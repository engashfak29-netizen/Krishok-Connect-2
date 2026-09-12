from __future__ import annotations
import os, sqlite3, json, hashlib, urllib.request, urllib.parse, re, hmac, time, uuid, logging, base64, secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import jwt
try:
    import redis
except Exception:
    redis = None
from .ingest_service import extract_file, chunk_text, keywords, sha256_file, SUPPORTED
from fastapi import FastAPI, HTTPException, Depends, Header, Query, UploadFile, File, WebSocket, WebSocketDisconnect, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from .production_services import send_push, sha256_bytes, signed_download_url, media_put, media_url
try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:
    psycopg = None
    dict_row = None

BASE=os.path.dirname(os.path.dirname(__file__))
PROJECT_ROOT=os.path.dirname(BASE)
WEB_DIR=os.path.join(PROJECT_ROOT,'web')
DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///./krishok_connect.db')
USE_POSTGRES=DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://')
DB=DATABASE_URL.replace('sqlite:///./','')
if not USE_POSTGRES and not os.path.isabs(DB): DB=os.path.join(BASE,DB)
SECRET=os.getenv('SECRET_KEY','dev-secret-change-me')
PRODUCTION_MODE=os.getenv('ENVIRONMENT','development').lower() in ('production','prod')
if PRODUCTION_MODE and (SECRET == 'dev-secret-change-me' or len(SECRET) < 32):
    raise RuntimeError('Production requires SECRET_KEY with at least 32 characters')
ALG='HS256'; pwd=CryptContext(schemes=['bcrypt'], deprecated='auto')
app=FastAPI(title='Krishok Connect API', version='2.0.0', docs_url='/docs' if os.getenv('ENABLE_API_DOCS','true').lower()=='true' else None, redoc_url=None)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['Permissions-Policy']='camera=(self), microphone=(self), geolocation=(self)'
        return response
app.add_middleware(SecurityHeadersMiddleware)

# Distributed abuse protection: Redis when configured, safe local fallback otherwise.
RATE_WINDOW=int(os.getenv('RATE_LIMIT_WINDOW_SECONDS','60'))
RATE_MAX=int(os.getenv('RATE_LIMIT_MAX_REQUESTS','120'))
REDIS_URL=os.getenv('REDIS_URL','').strip()
REQUIRE_REDIS=os.getenv('REQUIRE_REDIS','false').lower()=='true'
_redis=None
if REDIS_URL and redis is not None:
    try: _redis=redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    except Exception: _redis=None
if PRODUCTION_MODE and REQUIRE_REDIS and _redis is None:
    raise RuntimeError('Production requires a reachable REDIS_URL when REQUIRE_REDIS=true')
_rate_buckets={}
_rate_lock=__import__('threading').Lock()
logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'))
logger=logging.getLogger('krishok_connect')
def _rate_count(key):
    if _redis is not None:
        bucket=f'kc:rl:{key}'
        pipe=_redis.pipeline(); pipe.incr(bucket); pipe.expire(bucket,RATE_WINDOW+2)
        return int(pipe.execute()[0])
    with _rate_lock:
        _rate_buckets[key]=_rate_buckets.get(key,0)+1
        current=int(time.time())//RATE_WINDOW
        for k in list(_rate_buckets):
            if k[1] < current-1: _rate_buckets.pop(k,None)
        return _rate_buckets[key]
class RequestProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ip=request.client.host if request.client else 'unknown'
        key=(ip, int(time.time())//RATE_WINDOW)
        try: count=_rate_count(key)
        except Exception: count=1
        if count>RATE_MAX and request.url.path.startswith('/api/'):
            return JSONResponse({'detail':'অনেক বেশি অনুরোধ। কিছুক্ষণ পরে আবার চেষ্টা করুন।'},status_code=429,headers={'Retry-After':str(RATE_WINDOW)})
        request.state.request_id=uuid.uuid4().hex[:16]
        started=time.perf_counter()
        response=await call_next(request)
        response.headers['X-Request-ID']=request.state.request_id
        if request.url.path.startswith('/api/'):
            logger.info('%s %s %s %.1fms', request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
        return response
app.add_middleware(RequestProtectionMiddleware)
MEDIA_DIR=os.getenv('MEDIA_DIR',os.path.join(BASE,'media')); os.makedirs(MEDIA_DIR, exist_ok=True)
AI_INGEST_DIR=os.getenv('AI_INGEST_DIR', os.path.join(BASE,'ai_knowledge_uploads')); os.makedirs(AI_INGEST_DIR, exist_ok=True)
AI_MAX_FILE_MB=int(os.getenv('AI_MAX_FILE_MB','500'))
MEDIA_STORAGE_BACKEND=os.getenv('MEDIA_STORAGE_BACKEND','local').lower()
MEDIA_EXTERNAL_BASE_URL=os.getenv('MEDIA_EXTERNAL_BASE_URL','').strip()
MEDIA_SIGNING_SECRET=os.getenv('MEDIA_SIGNING_SECRET',SECRET)

class WSManager:
    def __init__(self): self.connections={}
    async def connect(self,cid,ws):
        await ws.accept(); self.connections.setdefault(cid,set()).add(ws)
    def disconnect(self,cid,ws):
        self.connections.get(cid,set()).discard(ws)
    async def broadcast(self,cid,payload):
        dead=[]
        for ws in list(self.connections.get(cid,set())):
            try: await ws.send_json(payload)
            except Exception: dead.append(ws)
        for ws in dead:self.disconnect(cid,ws)
ws_manager=WSManager()
origins=[x.strip() for x in os.getenv('CORS_ORIGINS','*').split(',') if x.strip()]
if PRODUCTION_MODE and ('*' in origins):
    raise RuntimeError('Production requires explicit CORS_ORIGINS; wildcard is not allowed')
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS'], allow_headers=['Authorization','Content-Type','Accept','X-Request-ID'])

def now(): return datetime.now(timezone.utc).isoformat()
def _pg_sql(sql):
    return sql.replace('?', '%s')
def conn():
    if USE_POSTGRES:
        if psycopg is None: raise RuntimeError('psycopg is required for PostgreSQL DATABASE_URL')
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def q(sql,args=(),one=False):
    c=conn(); cur=c.execute(_pg_sql(sql) if USE_POSTGRES else sql,args); rows=cur.fetchone() if one else cur.fetchall(); c.commit(); c.close(); return dict(rows) if one and rows else (None if one else [dict(x) for x in rows])
def init():
    c=conn(); schema='''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE, phone TEXT UNIQUE, password_hash TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'farmer', verified INTEGER DEFAULT 0, avatar TEXT, cover TEXT, location TEXT, division TEXT, district TEXT, upazila TEXT, union_name TEXT, area_name TEXT, bio TEXT, followers INTEGER DEFAULT 0, following INTEGER DEFAULT 0, rating REAL DEFAULT 0, rating_count INTEGER DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS auth_login_attempts(id TEXT PRIMARY KEY, identifier TEXT NOT NULL, ip TEXT NOT NULL, failed_count INTEGER NOT NULL DEFAULT 0, first_failed_at TEXT, locked_until TEXT, updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_auth_login_attempts_lookup ON auth_login_attempts(identifier,ip);
    CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,text TEXT NOT NULL,images TEXT DEFAULT '[]',likes INTEGER DEFAULT 0,shares INTEGER DEFAULT 0,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS post_likes(post_id TEXT,user_id TEXT,created_at TEXT NOT NULL,PRIMARY KEY(post_id,user_id),FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY,post_id TEXT NOT NULL,user_id TEXT NOT NULL,text TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS follows(follower_id TEXT,following_id TEXT,created_at TEXT NOT NULL,PRIMARY KEY(follower_id,following_id),FOREIGN KEY(follower_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(following_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,seller_id TEXT NOT NULL,name TEXT NOT NULL,price REAL NOT NULL,unit TEXT DEFAULT 'piece',category TEXT,stock REAL DEFAULT 0,location TEXT,description TEXT,tags TEXT DEFAULT '[]',images TEXT DEFAULT '[]',rating REAL DEFAULT 0,rating_count INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,FOREIGN KEY(seller_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS carts(user_id TEXT,product_id TEXT,quantity REAL NOT NULL,PRIMARY KEY(user_id,product_id),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,buyer_id TEXT NOT NULL,total REAL NOT NULL,status TEXT NOT NULL DEFAULT 'pending',payment_status TEXT NOT NULL DEFAULT 'unpaid',payment_method TEXT,delivery_address TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(buyer_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS order_items(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,product_id TEXT NOT NULL,seller_id TEXT NOT NULL,quantity REAL NOT NULL,unit_price REAL NOT NULL,FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,FOREIGN KEY(product_id) REFERENCES products(id),FOREIGN KEY(seller_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS conversation_members(conversation_id TEXT,user_id TEXT,PRIMARY KEY(conversation_id,user_id),FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,sender_id TEXT NOT NULL,text TEXT,attachment_url TEXT,read_at TEXT,created_at TEXT NOT NULL,FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,FOREIGN KEY(sender_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,text TEXT NOT NULL,kind TEXT DEFAULT 'general',read INTEGER DEFAULT 0,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS market_prices(id TEXT PRIMARY KEY,crop TEXT NOT NULL,market TEXT,price REAL NOT NULL,unit TEXT DEFAULT 'kg',date TEXT NOT NULL,source TEXT);
    CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,reporter_id TEXT NOT NULL,target_type TEXT NOT NULL,target_id TEXT NOT NULL,reason TEXT NOT NULL,status TEXT DEFAULT 'open',created_at TEXT NOT NULL,FOREIGN KEY(reporter_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS product_reviews(id TEXT PRIMARY KEY,product_id TEXT NOT NULL,reviewer_id TEXT NOT NULL,rating INTEGER NOT NULL,comment TEXT,created_at TEXT NOT NULL,UNIQUE(product_id,reviewer_id),FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,FOREIGN KEY(reviewer_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS weather_cache(id TEXT PRIMARY KEY,location TEXT NOT NULL,payload TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    '''
    if USE_POSTGRES:
        for statement in schema.split(';'):
            statement=statement.strip()
            if statement: c.execute(_pg_sql(statement))
    else:
        c.executescript(schema)
    c.commit(); c.close()
    # Additional production tables are created separately below.
init()

def _safe_add_column(table, column, ddl):
    try: q(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}')
    except Exception: pass

def ensure_extra_schema():
    # NEXT32 structured user location migration
    _safe_add_column('posts','videos',"TEXT DEFAULT '[]'")
    for col, ddl in [('division','TEXT'),('district','TEXT'),('upazila','TEXT'),('union_name','TEXT'),('area_name','TEXT')]:
        _safe_add_column('users', col, ddl)
    # Backward-compatible product tag migration for existing NEXT28 databases
    try:
        q("ALTER TABLE products ADD COLUMN tags TEXT DEFAULT '[]'")
    except Exception:
        pass
    # Seller pages, marketplace subscriptions, market areas and seller ads
    extra_market=[
      "CREATE TABLE IF NOT EXISTS seller_pages(id TEXT PRIMARY KEY,user_id TEXT NOT NULL UNIQUE,page_name TEXT NOT NULL,slug TEXT NOT NULL UNIQUE,description TEXT DEFAULT '',logo TEXT,cover TEXT,phone TEXT,location TEXT,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS seller_market_areas(id TEXT PRIMARY KEY,page_id TEXT NOT NULL,division TEXT,district TEXT,upazila TEXT,union_name TEXT,area_name TEXT,radius_km REAL,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(page_id) REFERENCES seller_pages(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS seller_subscription_plans(id TEXT PRIMARY KEY,name_bn TEXT NOT NULL,duration_days INTEGER NOT NULL,price REAL NOT NULL,ad_limit INTEGER DEFAULT 10,features TEXT DEFAULT '[]',active INTEGER DEFAULT 1,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS seller_subscriptions(id TEXT PRIMARY KEY,page_id TEXT NOT NULL,plan_id TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',payment_method TEXT,payment_reference TEXT,starts_at TEXT,expires_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(page_id) REFERENCES seller_pages(id) ON DELETE CASCADE,FOREIGN KEY(plan_id) REFERENCES seller_subscription_plans(id))",
      "CREATE TABLE IF NOT EXISTS seller_ads(id TEXT PRIMARY KEY,page_id TEXT NOT NULL,product_id TEXT,headline TEXT NOT NULL,description TEXT DEFAULT '',image TEXT,landing_url TEXT,area_id TEXT,status TEXT NOT NULL DEFAULT 'draft',starts_at TEXT,ends_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(page_id) REFERENCES seller_pages(id) ON DELETE CASCADE,FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL,FOREIGN KEY(area_id) REFERENCES seller_market_areas(id) ON DELETE SET NULL)",
      "CREATE INDEX IF NOT EXISTS idx_seller_pages_user ON seller_pages(user_id)",
      "CREATE INDEX IF NOT EXISTS idx_seller_ads_page_status ON seller_ads(page_id,status)",
      "CREATE TABLE IF NOT EXISTS inventory_ledger(id TEXT PRIMARY KEY,product_id TEXT NOT NULL,change_qty REAL NOT NULL,balance_qty REAL NOT NULL,reason TEXT NOT NULL,reference_type TEXT,reference_id TEXT,actor_id TEXT,created_at TEXT NOT NULL,FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE)",
      "CREATE INDEX IF NOT EXISTS idx_inventory_ledger_product_date ON inventory_ledger(product_id,created_at DESC)",
      "CREATE TABLE IF NOT EXISTS delivery_tracking(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,carrier TEXT,tracking_number TEXT,status TEXT NOT NULL DEFAULT 'pending',proof_url TEXT,updated_by TEXT,updated_at TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(order_id),FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS ai_farm_context_snapshots(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,context_json TEXT NOT NULL,source_version TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)",
      "CREATE INDEX IF NOT EXISTS idx_ai_farm_context_user_date ON ai_farm_context_snapshots(user_id,created_at DESC)",
      "CREATE TABLE IF NOT EXISTS farm_events(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,farm_id TEXT,plot_id TEXT,crop_instance_id TEXT,event_type TEXT NOT NULL,event_date TEXT NOT NULL,payload_json TEXT NOT NULL,source_journal_id TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)",
      "CREATE INDEX IF NOT EXISTS idx_farm_events_user_date ON farm_events(user_id,event_date DESC)"
    ]
    for stmt in extra_market:
        try: q(stmt)
        except Exception: pass
    logistics=[
      "CREATE TABLE IF NOT EXISTS order_status_history(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,status TEXT NOT NULL,note TEXT,actor_id TEXT,created_at TEXT NOT NULL,FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS order_returns(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,buyer_id TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'requested',refund_amount REAL DEFAULT 0,note TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,FOREIGN KEY(buyer_id) REFERENCES users(id) ON DELETE CASCADE)",
      "CREATE INDEX IF NOT EXISTS idx_user_area ON users(division,district,upazila,union_name,area_name)",
      "CREATE INDEX IF NOT EXISTS idx_order_returns_order ON order_returns(order_id,status)",
    ]
    for stmt in logistics:
        try: q(stmt)
        except Exception: pass
    try:
        if not q('SELECT id FROM seller_subscription_plans LIMIT 1',(),True):
            plans=[('7d','Starter — ৭ দিন',7,99,3),('30d','Standard — ৩০ দিন',30,299,15),('90d','Business — ৯০ দিন',90,699,50),('180d','Growth — ৬ মাস',180,1199,120),('365d','Premium — ১ বছর',365,1999,300)]
            for pid,name,dur,price,lim in plans:
                q('INSERT INTO seller_subscription_plans VALUES(?,?,?,?,?,?,?,?)',(pid,name,dur,price,lim,'[]',1,now()))
    except Exception: pass
    c=conn()
    statements=[
      "CREATE TABLE IF NOT EXISTS knowledge_documents(id TEXT PRIMARY KEY,title TEXT NOT NULL,content TEXT NOT NULL,source TEXT,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS knowledge_chunks(id TEXT PRIMARY KEY,document_id TEXT NOT NULL,content TEXT NOT NULL,keywords TEXT,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS audit_logs(id TEXT PRIMARY KEY,user_id TEXT,action TEXT NOT NULL,entity_type TEXT,entity_id TEXT,ip TEXT,metadata TEXT,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS market_sync_logs(id TEXT PRIMARY KEY,source TEXT NOT NULL,status TEXT NOT NULL,rows_imported INTEGER DEFAULT 0,error TEXT,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS device_tokens(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,token TEXT NOT NULL,platform TEXT,created_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,UNIQUE(user_id,token))",
      "CREATE TABLE IF NOT EXISTS call_events(id TEXT PRIMARY KEY,room_id TEXT NOT NULL,user_id TEXT NOT NULL,event TEXT NOT NULL,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS call_sessions(id TEXT PRIMARY KEY,room_id TEXT NOT NULL,caller_id TEXT NOT NULL,callee_id TEXT,call_type TEXT NOT NULL DEFAULT 'video',status TEXT NOT NULL DEFAULT 'ringing',started_at TEXT NOT NULL,answered_at TEXT,ended_at TEXT,ended_by TEXT,FOREIGN KEY(caller_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(callee_id) REFERENCES users(id) ON DELETE SET NULL)",
      "CREATE INDEX IF NOT EXISTS idx_call_sessions_room ON call_sessions(room_id,status)",
      "CREATE INDEX IF NOT EXISTS idx_call_sessions_callee ON call_sessions(callee_id,status)" ,
      "CREATE TABLE IF NOT EXISTS ai_ingestion_sources(id TEXT PRIMARY KEY,title TEXT NOT NULL,original_name TEXT NOT NULL,storage_path TEXT NOT NULL,mime_type TEXT,kind TEXT NOT NULL,sha256 TEXT NOT NULL UNIQUE,size_bytes INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'queued',created_by TEXT NOT NULL,error TEXT,metadata TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS ai_ingestion_chunks(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,chunk_index INTEGER NOT NULL,content TEXT NOT NULL,keywords TEXT,locator TEXT,created_at TEXT NOT NULL,FOREIGN KEY(source_id) REFERENCES ai_ingestion_sources(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS ai_diagnosis_cases(id TEXT PRIMARY KEY,title TEXT NOT NULL,crop TEXT,disease TEXT,pest TEXT,problem_type TEXT NOT NULL,symptoms TEXT NOT NULL,visual_signs TEXT,causes TEXT,actions TEXT,prevention TEXT,red_flags TEXT,source TEXT,confidence REAL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)",
      "CREATE INDEX IF NOT EXISTS idx_ai_diagnosis_crop_type ON ai_diagnosis_cases(crop,problem_type)",
      "CREATE INDEX IF NOT EXISTS idx_ai_diagnosis_disease ON ai_diagnosis_cases(disease)",
      "CREATE TABLE IF NOT EXISTS crop_categories(id TEXT PRIMARY KEY,name_bn TEXT NOT NULL,name_en TEXT,slug TEXT UNIQUE NOT NULL,sort_order INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS crops(id TEXT PRIMARY KEY,category_id TEXT NOT NULL,name_bn TEXT NOT NULL,name_en TEXT,slug TEXT UNIQUE NOT NULL,scientific_name TEXT,description TEXT,perennial INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(category_id) REFERENCES crop_categories(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS crop_varieties(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,name_bn TEXT NOT NULL,name_en TEXT,season TEXT,days_to_harvest INTEGER,min_temp REAL,max_temp REAL,notes TEXT,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS crop_regions(id TEXT PRIMARY KEY,name_bn TEXT NOT NULL,name_en TEXT,code TEXT UNIQUE,description TEXT,active INTEGER DEFAULT 1,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS crop_lifecycle_stages(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,variety_id TEXT,stage_name_bn TEXT NOT NULL,stage_name_en TEXT,age_start_day INTEGER,age_end_day INTEGER,stage_order INTEGER DEFAULT 0,season TEXT,description TEXT,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE,FOREIGN KEY(variety_id) REFERENCES crop_varieties(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS crop_management_rules(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,variety_id TEXT,stage_id TEXT,region_id TEXT,season TEXT,age_start_day INTEGER,age_end_day INTEGER,management_type TEXT NOT NULL,title_bn TEXT NOT NULL,instructions_bn TEXT NOT NULL,quantity_json TEXT,conditions_json TEXT,priority INTEGER DEFAULT 0,source TEXT,verified_at TEXT,status TEXT DEFAULT 'draft',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE,FOREIGN KEY(variety_id) REFERENCES crop_varieties(id) ON DELETE SET NULL,FOREIGN KEY(stage_id) REFERENCES crop_lifecycle_stages(id) ON DELETE SET NULL,FOREIGN KEY(region_id) REFERENCES crop_regions(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS crop_pests(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,name_bn TEXT NOT NULL,name_en TEXT,scientific_name TEXT,symptoms TEXT,early_warning TEXT,prevention TEXT,monitoring TEXT,source TEXT,status TEXT DEFAULT 'draft',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS crop_diseases(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,name_bn TEXT NOT NULL,name_en TEXT,pathogen TEXT,symptoms TEXT,visual_signs TEXT,early_warning TEXT,prevention TEXT,source TEXT,status TEXT DEFAULT 'draft',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS crop_problem_actions(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,pest_id TEXT,disease_id TEXT,stage_id TEXT,region_id TEXT,season TEXT,action_type TEXT NOT NULL,title_bn TEXT NOT NULL,action_bn TEXT NOT NULL,urgency TEXT DEFAULT 'normal',source TEXT,verified_at TEXT,status TEXT DEFAULT 'draft',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE,FOREIGN KEY(pest_id) REFERENCES crop_pests(id) ON DELETE CASCADE,FOREIGN KEY(disease_id) REFERENCES crop_diseases(id) ON DELETE CASCADE,FOREIGN KEY(stage_id) REFERENCES crop_lifecycle_stages(id) ON DELETE SET NULL,FOREIGN KEY(region_id) REFERENCES crop_regions(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS crop_treatments(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,pest_id TEXT,disease_id TEXT,product_name_bn TEXT,active_ingredient TEXT,formulation TEXT,registered_crop TEXT,target_name TEXT,dose_text TEXT,application_method TEXT,phi_days INTEGER,safety_text TEXT,registration_no TEXT,source TEXT,last_verified_at TEXT,status TEXT DEFAULT 'draft',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE,FOREIGN KEY(pest_id) REFERENCES crop_pests(id) ON DELETE SET NULL,FOREIGN KEY(disease_id) REFERENCES crop_diseases(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS crop_media(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,pest_id TEXT,disease_id TEXT,media_type TEXT NOT NULL,url TEXT NOT NULL,caption_bn TEXT,stage_id TEXT,source TEXT,verified_at TEXT,status TEXT DEFAULT 'draft',created_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE,FOREIGN KEY(pest_id) REFERENCES crop_pests(id) ON DELETE CASCADE,FOREIGN KEY(disease_id) REFERENCES crop_diseases(id) ON DELETE CASCADE,FOREIGN KEY(stage_id) REFERENCES crop_lifecycle_stages(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS crop_notification_rules(id TEXT PRIMARY KEY,crop_id TEXT NOT NULL,variety_id TEXT,stage_id TEXT,region_id TEXT,season TEXT,age_start_day INTEGER,age_end_day INTEGER,trigger_type TEXT NOT NULL,title_bn TEXT NOT NULL,message_template_bn TEXT NOT NULL,days_before INTEGER DEFAULT 0,priority INTEGER DEFAULT 0,enabled INTEGER DEFAULT 1,source TEXT,status TEXT DEFAULT 'draft',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE,FOREIGN KEY(variety_id) REFERENCES crop_varieties(id) ON DELETE SET NULL,FOREIGN KEY(stage_id) REFERENCES crop_lifecycle_stages(id) ON DELETE SET NULL,FOREIGN KEY(region_id) REFERENCES crop_regions(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS farmer_crop_profiles(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,crop_id TEXT NOT NULL,variety_id TEXT,region_id TEXT,season TEXT,planting_date TEXT,area_value REAL,area_unit TEXT DEFAULT 'decimal',notes TEXT,status TEXT DEFAULT 'active',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE CASCADE,FOREIGN KEY(variety_id) REFERENCES crop_varieties(id) ON DELETE SET NULL,FOREIGN KEY(region_id) REFERENCES crop_regions(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS crop_notification_log(id TEXT PRIMARY KEY,profile_id TEXT NOT NULL,rule_id TEXT NOT NULL,scheduled_for TEXT NOT NULL,sent_at TEXT,channel TEXT DEFAULT 'in_app',status TEXT DEFAULT 'pending',message TEXT,UNIQUE(profile_id,rule_id,scheduled_for),FOREIGN KEY(profile_id) REFERENCES farmer_crop_profiles(id) ON DELETE CASCADE,FOREIGN KEY(rule_id) REFERENCES crop_notification_rules(id) ON DELETE CASCADE)",
      "CREATE INDEX IF NOT EXISTS idx_crops_category ON crops(category_id,active)",
      "CREATE INDEX IF NOT EXISTS idx_crop_stages_age ON crop_lifecycle_stages(crop_id,age_start_day,age_end_day)",
      "CREATE INDEX IF NOT EXISTS idx_crop_rules_match ON crop_management_rules(crop_id,region_id,season,age_start_day,age_end_day,status)",
      "CREATE INDEX IF NOT EXISTS idx_crop_pests_crop ON crop_pests(crop_id,status)",
      "CREATE INDEX IF NOT EXISTS idx_crop_diseases_crop ON crop_diseases(crop_id,status)",
      "CREATE INDEX IF NOT EXISTS idx_crop_actions_match ON crop_problem_actions(crop_id,stage_id,region_id,season,status)",
      "CREATE INDEX IF NOT EXISTS idx_crop_treatments_match ON crop_treatments(crop_id,pest_id,disease_id,status)",
      "CREATE INDEX IF NOT EXISTS idx_crop_media_problem ON crop_media(crop_id,pest_id,disease_id,status)",
      "CREATE INDEX IF NOT EXISTS idx_crop_notify_match ON crop_notification_rules(crop_id,region_id,season,age_start_day,age_end_day,enabled)",
      "CREATE INDEX IF NOT EXISTS idx_farmer_crop_profiles_user ON farmer_crop_profiles(user_id,status)",
      "CREATE INDEX IF NOT EXISTS idx_crop_notification_log_profile ON crop_notification_log(profile_id,status,scheduled_for)",
      "CREATE TABLE IF NOT EXISTS farmer_farms(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,name TEXT NOT NULL DEFAULT 'আমার খামার',total_area_value REAL DEFAULT 0,total_area_unit TEXT DEFAULT 'decimal',soil_type TEXT,water_source TEXT,location TEXT,division TEXT,district TEXT,upazila TEXT,union_name TEXT,area_name TEXT,status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS farm_plots(id TEXT PRIMARY KEY,farm_id TEXT NOT NULL,name TEXT NOT NULL,area_value REAL NOT NULL,area_unit TEXT NOT NULL DEFAULT 'decimal',area_decimal REAL NOT NULL DEFAULT 0,land_type TEXT,soil_type TEXT,water_source TEXT,location TEXT,tenure TEXT,active INTEGER DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,closed_at TEXT,close_reason TEXT,FOREIGN KEY(farm_id) REFERENCES farmer_farms(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS plot_crops(id TEXT PRIMARY KEY,plot_id TEXT NOT NULL,crop_id TEXT,variety_id TEXT,crop_name TEXT NOT NULL,variety_name TEXT,planting_date TEXT,area_value REAL,area_unit TEXT DEFAULT 'decimal',area_decimal REAL,season TEXT,status TEXT NOT NULL DEFAULT 'active',harvest_date TEXT,notes TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(plot_id) REFERENCES farm_plots(id) ON DELETE CASCADE,FOREIGN KEY(crop_id) REFERENCES crops(id) ON DELETE SET NULL,FOREIGN KEY(variety_id) REFERENCES crop_varieties(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS farm_journal_entries(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,entry_text TEXT NOT NULL,source_type TEXT NOT NULL DEFAULT 'text',audio_path TEXT,parsed_json TEXT,parse_status TEXT NOT NULL DEFAULT 'pending',needs_confirmation INTEGER DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS farm_activity_records(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,plot_id TEXT,crop_instance_id TEXT,activity_type TEXT NOT NULL,activity_date TEXT NOT NULL,details TEXT NOT NULL,quantity_value REAL,quantity_unit TEXT,source_journal_id TEXT,confidence REAL DEFAULT 1.0,needs_confirmation INTEGER DEFAULT 0,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(plot_id) REFERENCES farm_plots(id) ON DELETE SET NULL,FOREIGN KEY(crop_instance_id) REFERENCES plot_crops(id) ON DELETE SET NULL,FOREIGN KEY(source_journal_id) REFERENCES farm_journal_entries(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS farm_input_records(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,plot_id TEXT,crop_instance_id TEXT,input_type TEXT NOT NULL,input_name TEXT NOT NULL,quantity_value REAL,quantity_unit TEXT,application_date TEXT,notes TEXT,source_journal_id TEXT,confidence REAL DEFAULT 1.0,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(plot_id) REFERENCES farm_plots(id) ON DELETE SET NULL,FOREIGN KEY(crop_instance_id) REFERENCES plot_crops(id) ON DELETE SET NULL,FOREIGN KEY(source_journal_id) REFERENCES farm_journal_entries(id) ON DELETE SET NULL)",
      "CREATE TABLE IF NOT EXISTS farm_area_history(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,farm_id TEXT NOT NULL,plot_id TEXT,change_type TEXT NOT NULL,old_area_value REAL,old_area_unit TEXT,old_area_decimal REAL,new_area_value REAL,new_area_unit TEXT,new_area_decimal REAL,reason TEXT,effective_date TEXT NOT NULL,source_journal_id TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(farm_id) REFERENCES farmer_farms(id) ON DELETE CASCADE,FOREIGN KEY(plot_id) REFERENCES farm_plots(id) ON DELETE SET NULL,FOREIGN KEY(source_journal_id) REFERENCES farm_journal_entries(id) ON DELETE SET NULL)",
      "CREATE INDEX IF NOT EXISTS idx_farmer_farms_user ON farmer_farms(user_id,status)",
      "CREATE INDEX IF NOT EXISTS idx_farm_plots_farm_active ON farm_plots(farm_id,active)",
      "CREATE INDEX IF NOT EXISTS idx_plot_crops_plot_status ON plot_crops(plot_id,status,planting_date)",
      "CREATE INDEX IF NOT EXISTS idx_farm_activity_user_date ON farm_activity_records(user_id,activity_date DESC)",
      "CREATE INDEX IF NOT EXISTS idx_farm_input_user_date ON farm_input_records(user_id,application_date DESC)",
      "CREATE INDEX IF NOT EXISTS idx_farm_area_history_farm_date ON farm_area_history(farm_id,effective_date DESC)",
      "CREATE INDEX IF NOT EXISTS idx_farm_journal_user_date ON farm_journal_entries(user_id,created_at DESC)",

    ]
    for st in statements: c.execute(_pg_sql(st) if USE_POSTGRES else st)
    c.commit(); c.close()
ensure_extra_schema()
# Production message delivery/read state migration.
_safe_add_column('messages','delivered_at','TEXT')
_safe_add_column('messages','edited_at','TEXT')
try:
    q('CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id,created_at DESC)')
except Exception: pass
try:
    q('CREATE INDEX IF NOT EXISTS idx_farm_events_user_date ON farm_events(user_id,event_date DESC)')
except Exception: pass
try:
    from .migrations import run_migrations
    run_migrations(DATABASE_URL)
except Exception as _migration_error:
    logger.warning('Migration runner skipped/failed: %s', _migration_error)

def ensure_indexes():
    c=conn()
    indexes=[
      'CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC)',
      'CREATE INDEX IF NOT EXISTS idx_products_seller_active ON products(seller_id,active)',
      'CREATE INDEX IF NOT EXISTS idx_orders_buyer_created ON orders(buyer_id,created_at DESC)',
      'CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)',
      'CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id,read,created_at DESC)',
      'CREATE INDEX IF NOT EXISTS idx_market_prices_crop_date ON market_prices(crop,date DESC)',
      'CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC)',
      'CREATE INDEX IF NOT EXISTS idx_ai_sources_status ON ai_ingestion_sources(status,created_at DESC)',
      'CREATE INDEX IF NOT EXISTS idx_ai_chunks_source ON ai_ingestion_chunks(source_id,chunk_index)'
    ]
    for st in indexes:
        try:c.execute(st)
        except Exception:pass
    c.commit();c.close()
ensure_indexes()

# --- Department + Role + Permission RBAC ---
RBAC_ROLES = {
    'super_admin': ('Super Admin','system'),
    'admin': ('Admin','administration'),
    'crop_admin': ('Crop Intelligence Staff','crop_intelligence'),
    'content_admin': ('AI Content Staff','ai_content'),
    'market_admin': ('Marketplace Staff','marketplace'),
    'finance_admin': ('Finance Staff','finance'),
    'support_admin': ('Support Staff','support'),
    'moderation_admin': ('Moderation Staff','moderation'),
    'farmer': ('Farmer','user'),
    'business': ('Business/Seller','user'),
    'expert': ('Agriculture Expert','user'),
}
RBAC_PERMISSIONS = [
    ('system.manage','System management'),('users.manage','User management'),
    ('admin.dashboard','Admin dashboard'),('reports.manage','Reports management'),
    ('analytics.view','Analytics view'),('audit.view','Audit log view'),
    ('crop.view','Crop intelligence view'),('crop.create','Crop intelligence create'),
    ('crop.edit','Crop intelligence edit'),('crop.approve','Crop intelligence approve'),
    ('crop.delete','Crop intelligence delete'),('ai.knowledge.manage','AI knowledge management'),
    ('ai.diagnosis.manage','AI diagnosis management'),('marketplace.manage','Marketplace management'),
    ('finance.manage','Finance management'),('support.manage','Support management'),
    ('moderation.manage','Moderation management'),
]
RBAC_ROLE_PERMS = {
    'super_admin': {p[0] for p in RBAC_PERMISSIONS},
    'admin': {'admin.dashboard','users.manage','reports.manage','analytics.view','audit.view'},
    'crop_admin': {'admin.dashboard','crop.view','crop.create','crop.edit','crop.approve','crop.delete'},
    'content_admin': {'admin.dashboard','ai.knowledge.manage','ai.diagnosis.manage'},
    'market_admin': {'admin.dashboard','marketplace.manage','reports.manage','analytics.view'},
    'finance_admin': {'admin.dashboard','finance.manage','analytics.view','audit.view'},
    'support_admin': {'admin.dashboard','support.manage','users.manage'},
    'moderation_admin': {'admin.dashboard','moderation.manage','reports.manage'},
    'farmer': set(), 'business': set(), 'expert': set(),
}

# Strict department isolation: a department role may only receive permissions
# belonging to its own operational domain (plus the shared dashboard view).
DEPARTMENT_PERMISSION_PREFIX = {
    'crop_admin': {'crop.'},
    'content_admin': {'ai.knowledge.', 'ai.diagnosis.'},
    'market_admin': {'marketplace.', 'reports.', 'analytics.'},
    'finance_admin': {'finance.', 'analytics.', 'audit.'},
    'support_admin': {'support.', 'users.'},
    'moderation_admin': {'moderation.', 'reports.'},
    'admin': {'admin.', 'users.', 'reports.', 'analytics.', 'audit.'},
}

def allowed_permissions_for_role(role_slug):
    if role_slug == 'super_admin': return {p[0] for p in RBAC_PERMISSIONS}
    prefixes=DEPARTMENT_PERMISSION_PREFIX.get(role_slug,set())
    return {p[0] for p in RBAC_PERMISSIONS if any(p[0].startswith(x) for x in prefixes)} | ({'admin.dashboard'} if role_slug in RBAC_ROLE_PERMS else set())

def uid(prefix='u'): return prefix+secrets.token_hex(8)

def ensure_rbac_schema():
    c=conn()
    statements=[
      "CREATE TABLE IF NOT EXISTS roles(id TEXT PRIMARY KEY,slug TEXT UNIQUE NOT NULL,name TEXT NOT NULL,department TEXT NOT NULL,active INTEGER DEFAULT 1,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS permissions(id TEXT PRIMARY KEY,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS role_permissions(role_id TEXT NOT NULL,permission_id TEXT NOT NULL,PRIMARY KEY(role_id,permission_id),FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE,FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE)",
      "CREATE TABLE IF NOT EXISTS user_roles(user_id TEXT NOT NULL,role_id TEXT NOT NULL,is_primary INTEGER DEFAULT 1,created_at TEXT NOT NULL,PRIMARY KEY(user_id,role_id),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE)",
      "CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id,is_primary)",
      "CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id)",
      "CREATE TABLE IF NOT EXISTS staff_accounts(user_id TEXT PRIMARY KEY,active INTEGER DEFAULT 1,locked_until TEXT,updated_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)",
      "CREATE INDEX IF NOT EXISTS idx_staff_accounts_active ON staff_accounts(active)",
      "CREATE TABLE IF NOT EXISTS staff_work_owners(department TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,owner_user_id TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(department,entity_type,entity_id),FOREIGN KEY(owner_user_id) REFERENCES users(id) ON DELETE CASCADE)",
      "CREATE INDEX IF NOT EXISTS idx_staff_work_owners_owner ON staff_work_owners(owner_user_id,department)",
    ]
    for st in statements:
        try: c.execute(_pg_sql(st) if USE_POSTGRES else st)
        except Exception: pass
    ts=now()
    for slug,(name,dept) in RBAC_ROLES.items():
        existing=c.execute(_pg_sql('SELECT id FROM roles WHERE slug=?') if USE_POSTGRES else 'SELECT id FROM roles WHERE slug=?',(slug,)).fetchone()
        if not existing:
            c.execute(_pg_sql('INSERT INTO roles VALUES(?,?,?,?,?,?)') if USE_POSTGRES else 'INSERT INTO roles VALUES(?,?,?,?,?,?)',(uid('role'),slug,name,dept,1,ts))
    for code,name in RBAC_PERMISSIONS:
        existing=c.execute(_pg_sql('SELECT id FROM permissions WHERE code=?') if USE_POSTGRES else 'SELECT id FROM permissions WHERE code=?',(code,)).fetchone()
        if not existing:
            c.execute(_pg_sql('INSERT INTO permissions VALUES(?,?,?,?)') if USE_POSTGRES else 'INSERT INTO permissions VALUES(?,?,?,?)',(uid('perm'),code,name,ts))
    for slug,codes in RBAC_ROLE_PERMS.items():
        role=c.execute(_pg_sql('SELECT id FROM roles WHERE slug=?') if USE_POSTGRES else 'SELECT id FROM roles WHERE slug=?',(slug,)).fetchone()
        if not role: continue
        rid=role[0] if not isinstance(role,dict) else role['id']
        for code in codes:
            perm=c.execute(_pg_sql('SELECT id FROM permissions WHERE code=?') if USE_POSTGRES else 'SELECT id FROM permissions WHERE code=?',(code,)).fetchone()
            if not perm: continue
            pid=perm[0] if not isinstance(perm,dict) else perm['id']
            try: c.execute(_pg_sql('INSERT INTO role_permissions(role_id,permission_id) VALUES(?,?)') if USE_POSTGRES else 'INSERT OR IGNORE INTO role_permissions(role_id,permission_id) VALUES(?,?)',(rid,pid))
            except Exception: pass
    # Migrate existing users into the new RBAC table without changing their legacy type.
    users=c.execute('SELECT id,type FROM users').fetchall()
    for row in users:
        uidv=row[0] if not isinstance(row,dict) else row['id']; typ=row[1] if not isinstance(row,dict) else row['type']
        slug=typ if typ in RBAC_ROLES else 'farmer'
        role=c.execute(_pg_sql('SELECT id FROM roles WHERE slug=?') if USE_POSTGRES else 'SELECT id FROM roles WHERE slug=?',(slug,)).fetchone()
        if role:
            rid=role[0] if not isinstance(role,dict) else role['id']
            try: c.execute(_pg_sql('INSERT INTO user_roles(user_id,role_id,is_primary,created_at) VALUES(?,?,1,?)') if USE_POSTGRES else 'INSERT OR IGNORE INTO user_roles(user_id,role_id,is_primary,created_at) VALUES(?,?,1,?)',(uidv,rid,ts))
            except Exception: pass
    # Every management account gets an explicit operational status row.
    staff_rows=c.execute("SELECT id FROM users WHERE type IN ('admin','super_admin','crop_admin','content_admin','market_admin','finance_admin','support_admin','moderation_admin')").fetchall()
    for row in staff_rows:
        uidv=row[0] if not isinstance(row,dict) else row['id']
        try:
            c.execute(_pg_sql('INSERT INTO staff_accounts(user_id,active,locked_until,updated_at) VALUES(?,?,?,?)') if USE_POSTGRES else 'INSERT OR IGNORE INTO staff_accounts(user_id,active,locked_until,updated_at) VALUES(?,?,?,?)',(uidv,1,None,ts))
        except Exception: pass
    c.commit(); c.close()

def role_slugs(u):
    return [x['slug'] for x in q('SELECT r.slug FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=? ORDER BY ur.is_primary DESC,r.slug',(u['id'],))]

def permission_codes(u):
    return [x['code'] for x in q('SELECT DISTINCT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id JOIN user_roles ur ON ur.role_id=rp.role_id WHERE ur.user_id=?',(u['id'],))]

def me(authorization: Optional[str]=Header(None)): return user_from_token(authorization)

def require_permission(code):
    def dep(u=Depends(me)):
        if code not in permission_codes(u): raise HTTPException(403,'এই কাজের অনুমতি আপনার নেই')
        return u
    return dep

def require_role(slug):
    def dep(u=Depends(me)):
        if slug not in role_slugs(u): raise HTTPException(403,'এই বিভাগে প্রবেশের অনুমতি আপনার নেই')
        return u
    return dep

def require_super_admin(u=Depends(me)):
    if 'super_admin' not in role_slugs(u): raise HTTPException(403,'Super Admin access required')
    return u

def knowledge_admin(u=Depends(me)):
    if not set(('crop.view','crop.create','crop.edit','crop.approve')) & set(permission_codes(u)):
        raise HTTPException(403,'Crop Intelligence access required')
    return u

def require_admin(u=Depends(me)):
    if not any(r in role_slugs(u) for r in ('admin','super_admin')):
        raise HTTPException(403,'Admin access required')
    return u

def primary_staff_role(u):
    roles=role_slugs(u)
    for r in ('super_admin','admin','crop_admin','content_admin','market_admin','finance_admin','support_admin','moderation_admin'):
        if r in roles: return r
    return None

def require_department(role_slug):
    def dep(u=Depends(me)):
        if primary_staff_role(u) not in (role_slug,'admin','super_admin'):
            raise HTTPException(403,'এই বিভাগের data-তে আপনার অনুমতি নেই')
        return u
    return dep

def require_owner_or_elevated(table, record_id, owner_column='created_by', u=None):
    if u is None: raise HTTPException(403,'Access denied')
    if primary_staff_role(u) in ('super_admin','admin'): return u
    row=q(f'SELECT {owner_column} FROM {table} WHERE id=?',(record_id,),True)
    if not row: raise HTTPException(404,'Record not found')
    if row.get(owner_column)!=u['id']: raise HTTPException(403,'অন্য Staff-এর কাজ edit করার অনুমতি নেই')
    return u

def enforce_work_owner(department, entity_type, entity_id, u):
    """Same-department staff can view shared work, but only its owner can mutate it.
    Unassigned legacy records are claimed on first staff mutation; Admin/Super Admin bypass ownership.
    """
    r=primary_staff_role(u)
    if r in ('super_admin','admin'): return
    if r != department: raise HTTPException(403,'অন্য বিভাগের কাজের অনুমতি নেই')
    row=q('SELECT owner_user_id FROM staff_work_owners WHERE department=? AND entity_type=? AND entity_id=?',(department,entity_type,entity_id),True)
    if row and row.get('owner_user_id') != u['id']:
        raise HTTPException(403,'এই কাজটি অন্য Staff-এর নামে বরাদ্দ আছে; আপনি শুধু দেখতে পারবেন')
    if not row:
        ts=now()
        q('INSERT INTO staff_work_owners(department,entity_type,entity_id,owner_user_id,created_at,updated_at) VALUES(?,?,?,?,?,?)',(department,entity_type,entity_id,u['id'],ts,ts))

# --- Seller order management ---
@app.get('/api/v1/seller/orders')
def seller_orders(u=Depends(me)):
    rows=q("SELECT DISTINCT o.* FROM orders o JOIN order_items oi ON oi.order_id=o.id WHERE oi.seller_id=? ORDER BY o.created_at DESC",(u['id'],))
    for o in rows: o['items']=q('SELECT oi.*,p.name FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=? AND oi.seller_id=?',(o['id'],u['id']))
    return rows

# --- Inventory ledger + delivery tracking ---
@app.post('/api/v1/seller/products/{product_id}/inventory-adjust')
def adjust_inventory(product_id:str,change_qty:float=Query(...),reason:str=Query(...),u=Depends(me)):
    p=q('SELECT * FROM products WHERE id=? AND seller_id=?',(product_id,u['id']),True)
    if not p: raise HTTPException(404,'Product not found')
    new_balance=float(p['stock'] or 0)+change_qty
    if new_balance<0: raise HTTPException(409,'Inventory cannot become negative')
    q('UPDATE products SET stock=? WHERE id=?',(new_balance,product_id))
    lid=uid('inv'); q('INSERT INTO inventory_ledger VALUES(?,?,?,?,?,?,?, ?,?)',(lid,product_id,change_qty,new_balance,reason,None,None,u['id'],now()))
    return q('SELECT * FROM inventory_ledger WHERE id=?',(lid,),True)

@app.get('/api/v1/seller/products/{product_id}/inventory-ledger')
def inventory_ledger(product_id:str,u=Depends(me)):
    if not q('SELECT id FROM products WHERE id=? AND seller_id=?',(product_id,u['id']),True): raise HTTPException(404,'Product not found')
    return q('SELECT * FROM inventory_ledger WHERE product_id=? ORDER BY created_at DESC LIMIT 500',(product_id,))

@app.get('/api/v1/orders/{order_id}/delivery')
def get_delivery(order_id:str,u=Depends(me)):
    o=q('SELECT * FROM orders WHERE id=?',(order_id,),True)
    if not o: raise HTTPException(404,'Order not found')
    allowed=o['buyer_id']==u['id'] or bool(q('SELECT 1 FROM order_items WHERE order_id=? AND seller_id=?',(order_id,u['id']),True)) or u['type'] in ('admin','super_admin')
    if not allowed: raise HTTPException(403,'Not allowed')
    return q('SELECT * FROM delivery_tracking WHERE order_id=?',(order_id,),True)

@app.patch('/api/v1/seller/orders/{order_id}/delivery')
def update_delivery(order_id:str,x:DeliveryTrackingIn,u=Depends(me)):
    if not q('SELECT 1 FROM order_items WHERE order_id=? AND seller_id=?',(order_id,u['id']),True) and u['type'] not in ('admin','super_admin'): raise HTTPException(403,'Not allowed')
    row=q('SELECT * FROM delivery_tracking WHERE order_id=?',(order_id,),True); ts=now()
    if row: q('UPDATE delivery_tracking SET carrier=?,tracking_number=?,status=?,proof_url=?,updated_by=?,updated_at=? WHERE order_id=?',(x.carrier,x.tracking_number,x.status,_safe_profile_url(x.proof_url),u['id'],ts,order_id))
    else: q('INSERT INTO delivery_tracking VALUES(?,?,?,?,?,?,?,?,?)',(uid('dtg'),order_id,x.carrier,x.tracking_number,x.status,_safe_profile_url(x.proof_url),u['id'],ts,ts))
    return q('SELECT * FROM delivery_tracking WHERE order_id=?',(order_id,),True)

# --- Product ratings/reviews ---
@app.get('/api/v1/products/{product_id}/reviews')
def product_reviews(product_id:str,u=Depends(me)):
    if not q('SELECT id FROM products WHERE id=?',(product_id,),True): raise HTTPException(404,'Product not found')
    return q('SELECT r.*,u.name,u.avatar FROM product_reviews r JOIN users u ON u.id=r.reviewer_id WHERE r.product_id=? ORDER BY r.created_at DESC',(product_id,))

@app.post('/api/v1/products/{product_id}/reviews')
def add_product_review(product_id:str,x:RatingIn,u=Depends(me)):
    if not q('SELECT id FROM products WHERE id=?',(product_id,),True): raise HTTPException(404,'Product not found')
    bought=q("SELECT 1 FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.product_id=? AND o.buyer_id=? AND o.status='delivered' LIMIT 1",(product_id,u['id']),True)
    if not bought: raise HTTPException(403,'Delivered order required before reviewing')
    rid=uid('rv')
    try: q('INSERT INTO product_reviews VALUES(?,?,?,?,?,?)',(rid,product_id,u['id'],x.rating,x.comment,now()))
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower() or isinstance(e, sqlite3.IntegrityError): raise HTTPException(409,'আপনি ইতিমধ্যে এই পণ্যে রিভিউ দিয়েছেন')
        raise
    agg=q('SELECT AVG(rating) avg,COUNT(*) n FROM product_reviews WHERE product_id=?',(product_id,),True)
    q('UPDATE products SET rating=?,rating_count=? WHERE id=?',(round(agg['avg'] or 0,2),agg['n'],product_id))
    return q('SELECT r.*,u.name,u.avatar FROM product_reviews r JOIN users u ON u.id=r.reviewer_id WHERE r.id=?',(rid,),True)

# --- WebRTC signaling channel (media stays peer-to-peer) ---
call_connections={}
@app.post('/api/v1/notifications/device-token')
def register_device_token(x:DeviceTokenIn,u=Depends(me)):
    t=uid('dt'); ts=now(); q('INSERT INTO device_tokens VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,token) DO UPDATE SET platform=excluded.platform,last_seen_at=excluded.last_seen_at',(t,u['id'],x.token,x.platform,ts,ts)); return {'ok':True}

@app.delete('/api/v1/notifications/device-token')
def unregister_device_token(token:str,u=Depends(me)):
    q('DELETE FROM device_tokens WHERE user_id=? AND token=?',(u['id'],token)); return {'ok':True}

class CallCreate(BaseModel):
    peer_user_id:str
    call_type:str='video'

class CallState(BaseModel):
    status:str

@app.post('/api/v1/calls')
def create_call(x:CallCreate,u=Depends(me)):
    if x.peer_user_id==u['id']: raise HTTPException(400,'নিজেকে কল করা যাবে না')
    peer=q('SELECT id FROM users WHERE id=?',(x.peer_user_id,),True)
    if not peer: raise HTTPException(404,'কল গ্রহণকারী পাওয়া যায়নি')
    if x.call_type not in ('audio','video'): raise HTTPException(422,'Invalid call type')
    active=q("SELECT * FROM call_sessions WHERE (caller_id=? OR callee_id=?) AND status IN ('ringing','connected') ORDER BY started_at DESC LIMIT 1",(u['id'],u['id']),True)
    if active: raise HTTPException(409,'আপনার একটি কল ইতিমধ্যে চলছে')
    cid=uid('call'); room='call-'+cid; ts=now()
    q('INSERT INTO call_sessions(id,room_id,caller_id,callee_id,call_type,status,started_at) VALUES(?,?,?,?,?,?,?)',(cid,room,u['id'],x.peer_user_id,x.call_type,'ringing',ts))
    q('INSERT INTO call_events VALUES(?,?,?,?,?)',(uid('ce'),room,u['id'],'ringing',ts))
    q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),x.peer_user_id,f'{u["name"]} আপনাকে {"ভিডিও" if x.call_type=="video" else "অডিও"} কল করছেন','incoming_call',0,ts))
    return {'id':cid,'room_id':room,'call_type':x.call_type,'status':'ringing','peer':public_user(q('SELECT * FROM users WHERE id=?',(x.peer_user_id,),True))}

@app.get('/api/v1/calls/incoming')
def incoming_calls(u=Depends(me)):
    return q("SELECT c.*,u.name caller_name,u.avatar caller_avatar FROM call_sessions c JOIN users u ON u.id=c.caller_id WHERE c.callee_id=? AND c.status='ringing' ORDER BY c.started_at DESC LIMIT 10",(u['id'],))

@app.get('/api/v1/calls/{call_id}')
def get_call(call_id:str,u=Depends(me)):
    c=q('SELECT * FROM call_sessions WHERE id=?',(call_id,),True)
    if not c: raise HTTPException(404,'Call not found')
    if u['id'] not in (c['caller_id'],c['callee_id']): raise HTTPException(403,'Not allowed')
    return c

@app.patch('/api/v1/calls/{call_id}')
def update_call(call_id:str,x:CallState,u=Depends(me)):
    c=q('SELECT * FROM call_sessions WHERE id=?',(call_id,),True)
    if not c: raise HTTPException(404,'Call not found')
    if u['id'] not in (c['caller_id'],c['callee_id']): raise HTTPException(403,'Not allowed')
    if x.status not in ('connected','rejected','ended','missed','cancelled'): raise HTTPException(422,'Invalid call status')
    if c['status'] in ('ended','rejected','missed','cancelled'): return c
    ts=now(); answered=ts if x.status=='connected' else c.get('answered_at'); ended=ts if x.status in ('ended','rejected','missed','cancelled') else c.get('ended_at')
    q('UPDATE call_sessions SET status=?,answered_at=?,ended_at=?,ended_by=? WHERE id=?',(x.status,answered,ended,u['id'] if ended else c.get('ended_by'),call_id))
    q('INSERT INTO call_events VALUES(?,?,?,?,?)',(uid('ce'),c['room_id'],u['id'],x.status,ts))
    other=c['callee_id'] if u['id']==c['caller_id'] else c['caller_id']
    if other: q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),other,f'কলের অবস্থা: {x.status}','call',0,ts))
    return q('SELECT * FROM call_sessions WHERE id=?',(call_id,),True)

@app.get('/api/v1/calls/{call_id}/events')
def call_events(call_id:str,u=Depends(me)):
    c=q('SELECT * FROM call_sessions WHERE id=?',(call_id,),True)
    if not c or u['id'] not in (c['caller_id'],c['callee_id']): raise HTTPException(403,'Not allowed')
    return q('SELECT * FROM call_events WHERE room_id=? ORDER BY created_at',(c['room_id'],))

@app.get('/api/v1/calls/config')
def call_config(u=Depends(me)):
    # TURN credentials are supplied only through server environment; never hard-code secrets.
    raw=os.getenv('TURN_SERVERS_JSON','').strip()
    if raw:
        try: return {'ice_servers':json.loads(raw)}
        except Exception: raise HTTPException(500,'TURN_SERVERS_JSON is invalid')
    return {'ice_servers':[]}

@app.websocket('/ws/calls/{room_id}')
async def calls(room_id:str, websocket:WebSocket, authorization:Optional[str]=Query(None), token:Optional[str]=Query(None)):
    try:
        auth=authorization or (('Bearer '+token) if token else None)
        user=user_from_token(auth)
        call=q("SELECT * FROM call_sessions WHERE room_id=? AND (caller_id=? OR callee_id=?) AND status IN ('ringing','connected') ORDER BY started_at DESC LIMIT 1",(room_id,user['id'],user['id']),True)
        if not call: await websocket.close(code=4403); return
    except HTTPException: await websocket.close(code=1008); return
    await websocket.accept(); call_connections.setdefault(room_id,set()).add(websocket)
    try:
        while True:
            message=await websocket.receive_json()
            payload={'type':message.get('type','signal'),'from':user['id'],'payload':message.get('payload')}
            for peer in list(call_connections.get(room_id,set())):
                if peer is not websocket:
                    try: await peer.send_json(payload)
                    except Exception: pass
    except WebSocketDisconnect: pass
    finally: call_connections.get(room_id,set()).discard(websocket)

@app.get('/api/v1/orders/{order_id}')
def order_detail(order_id:str,u=Depends(me)):
    o=q('SELECT * FROM orders WHERE id=?',(order_id,),True)
    if not o: raise HTTPException(404,'Order not found')
    owned=o['buyer_id']==u['id'] or bool(q('SELECT 1 FROM order_items WHERE order_id=? AND seller_id=?',(order_id,u['id']),True)) or u['type'] in ('admin','super_admin')
    if not owned: raise HTTPException(403,'Not allowed')
    o['items']=q('SELECT oi.*,p.name FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?',(order_id,)); return o

# --- Seller product management ---
class ProductActiveUpdate(BaseModel):
    active: bool

@app.get('/api/v1/seller/products')
def seller_products(u=Depends(me)):
    rows=q('SELECT * FROM products WHERE seller_id=? ORDER BY created_at DESC',(u['id'],))
    for p in rows:
        p['images']=json.loads(p['images'])
    return rows

@app.patch('/api/v1/products/{product_id}/active')
def product_active(product_id:str,x:ProductActiveUpdate,u=Depends(me)):
    p=q('SELECT * FROM products WHERE id=?',(product_id,),True)
    if not p: raise HTTPException(404,'Product not found')
    if p['seller_id']!=u['id'] and u['type'] not in ('admin','super_admin'):
        raise HTTPException(403,'Not allowed')
    q('UPDATE products SET active=? WHERE id=?',(1 if x.active else 0,product_id))
    return product(product_id,u)

@app.delete('/api/v1/products/{product_id}')
def delete_product(product_id:str,u=Depends(me)):
    p=q('SELECT * FROM products WHERE id=?',(product_id,),True)
    if not p: raise HTTPException(404,'Product not found')
    if p['seller_id']!=u['id'] and u['type'] not in ('admin','super_admin'):
        raise HTTPException(403,'Not allowed')
    # Keep historical order items intact; deactivate instead of hard-delete when referenced.
    used=q('SELECT id FROM order_items WHERE product_id=? LIMIT 1',(product_id,),True)
    if used:
        q('UPDATE products SET active=0 WHERE id=?',(product_id,))
        return {'deleted':False,'deactivated':True,'message':'অর্ডার ইতিহাস থাকায় পণ্যটি নিষ্ক্রিয় করা হয়েছে'}
    q('DELETE FROM products WHERE id=?',(product_id,))
    return {'deleted':True}

# --- Payment status helpers (gateway callback can update this later) ---
@app.get('/api/v1/admin/analytics')
def admin_analytics(u=Depends(require_admin)):
    def n(sql): return q(sql,(),True)['n']
    return {
      'users':n('SELECT COUNT(*) n FROM users'),'verified_users':n('SELECT COUNT(*) n FROM users WHERE verified=1'),
      'posts':n('SELECT COUNT(*) n FROM posts'),'products':n('SELECT COUNT(*) n FROM products WHERE active=1'),
      'orders':n('SELECT COUNT(*) n FROM orders'),'pending_orders':n("SELECT COUNT(*) n FROM orders WHERE status IN ('pending','confirmed','processing','shipped')"),
      'open_reports':n("SELECT COUNT(*) n FROM reports WHERE status='open'"),'unread_notifications':n('SELECT COUNT(*) n FROM notifications WHERE read=0'),
      'unread_notifications':n('SELECT COUNT(*) n FROM notifications WHERE read=0')
    }

@app.get('/api/v1/admin/audit-logs')
def admin_audit_logs(limit:int=100,u=Depends(require_admin)):
    return q('SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?',(max(1,min(limit,500)),))




# --- Production backend services (NEXT40) ---
@app.get('/media/{object_key:path}')
def serve_media(object_key:str,authorization:Optional[str]=Header(None)):
    if not re.fullmatch(r'[A-Za-z0-9._-]+', object_key): raise HTTPException(404,'Media not found')
    row=q('SELECT * FROM media_assets WHERE object_key=?',(object_key,),True)
    if not row: raise HTTPException(404,'Media not found')
    public_ref=bool(q('SELECT id FROM posts WHERE images LIKE ? OR videos LIKE ? LIMIT 1',(f'%{object_key}%',f'%{object_key}%'),True))
    public_ref=public_ref or bool(q('SELECT id FROM products WHERE images LIKE ? LIMIT 1',(f'%{object_key}%',),True))
    public_ref=public_ref or bool(q('SELECT id FROM crop_media WHERE url LIKE ? AND status=? LIMIT 1',(f'%{object_key}%','approved'),True))
    u=None
    if authorization:
        try: u=user_from_token(authorization)
        except HTTPException: u=None
    if not public_ref and (not u or (row.get('user_id')!=u['id'] and u['type'] not in ('admin','super_admin'))):
        raise HTTPException(401 if not u else 403,'Authentication required' if not u else 'Not allowed')
    if row.get('storage_backend')=='external':
        try: url=media_url(row['object_key'])
        except Exception as e: raise HTTPException(503,f'External media URL unavailable: {str(e)[:180]}')
        return RedirectResponse(url=url,status_code=307)
    path=os.path.join(MEDIA_DIR, object_key)
    if not os.path.isfile(path): raise HTTPException(404,'Media file not found')
    return FileResponse(path, media_type=row.get('mime_type') or 'application/octet-stream', filename=row.get('original_name') or object_key)

class MediaRegisterIn(BaseModel):
    object_key:str=Field(min_length=1,max_length=500)
    original_name:Optional[str]=None
    mime_type:Optional[str]=None
    size_bytes:int=Field(ge=0)
    sha256:str=Field(min_length=64,max_length=64)

@app.post('/api/v1/media/register')
def register_media(x:MediaRegisterIn,u=Depends(me)):
    if MEDIA_STORAGE_BACKEND not in ('local','external'):
        raise HTTPException(500,'Invalid MEDIA_STORAGE_BACKEND')
    existing=q('SELECT * FROM media_assets WHERE object_key=?',(x.object_key,),True)
    if existing and existing.get('user_id')!=u['id']:
        raise HTTPException(403,'Media object belongs to another user')
    mid=existing['id'] if existing else uid('media'); ts=now()
    if existing:
        q('UPDATE media_assets SET original_name=?,mime_type=?,size_bytes=?,sha256=? WHERE id=?',(x.original_name,x.mime_type,x.size_bytes,x.sha256,mid))
    else:
        q('INSERT INTO media_assets VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,u['id'],x.object_key,x.original_name,x.mime_type,x.size_bytes,x.sha256,MEDIA_STORAGE_BACKEND,ts))
    return media_asset(mid,u)

def media_asset(mid,u):
    row=q('SELECT * FROM media_assets WHERE id=?',(mid,),True)
    if not row: raise HTTPException(404,'Media not found')
    if row.get('user_id')!=u['id'] and u['type'] not in ('admin','super_admin'):
        raise HTTPException(403,'Not allowed')
    row['url']=media_url(row['object_key'])
    return row

@app.get('/api/v1/media/{media_id}')
def get_media(media_id:str,u=Depends(me)): return media_asset(media_id,u)

class PushEnqueueIn(BaseModel):
    user_id:str
    title:str=Field(min_length=1,max_length=200)
    body:str=Field(min_length=1,max_length=2000)
    data:dict[str,Any]={}


def ensure_management_active(u):
    if _is_management_role(''.join(role_slugs(u)) if False else (role_slugs(u)[0] if role_slugs(u) else '')):
        st=q('SELECT active,locked_until FROM staff_accounts WHERE user_id=?',(u['id'],),True)
        if st and not st['active']: raise HTTPException(403,'Management account is disabled')
        if st and st.get('locked_until'):
            try:
                if datetime.fromisoformat(st['locked_until']) > datetime.now(timezone.utc): raise HTTPException(423,'Management account temporarily locked')
            except ValueError: pass
    return u

ensure_rbac_schema()
try:
    from .crop_seed import seed_crop_catalog
    seed_crop_catalog()
except Exception as e:
    logger.warning('crop catalog seed skipped: %s',e)

def token_for(user):
    tid=secrets.token_hex(12); exp=datetime.now(timezone.utc)+timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES','10080')))
    q('INSERT INTO sessions(token_id,user_id,expires_at,created_at) VALUES(?,?,?,?)',(tid,user['id'],exp.isoformat(),now()))
    return jwt.encode({'sub':user['id'],'sid':tid,'exp':exp},SECRET,algorithm=ALG)
def user_from_token(authorization: Optional[str]):
    if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401,'Authentication required')
    try: p=jwt.decode(authorization.split(' ',1)[1],SECRET,algorithms=[ALG]); u=q('SELECT * FROM users WHERE id=?',(p['sub'],),True)
    except Exception: raise HTTPException(401,'Invalid or expired token')
    if not u: raise HTTPException(401,'User not found')
    sid=p.get('sid')
    if sid and not q('SELECT token_id FROM sessions WHERE token_id=? AND user_id=? AND expires_at>?',(sid,u['id'],now()),True):
        raise HTTPException(401,'Session expired or logged out')
    # Management sessions are invalidated centrally when a staff account is disabled.
    if 'staff_accounts' in globals() if False else True:
        try:
            st=q('SELECT active FROM staff_accounts WHERE user_id=?',(u['id'],),True)
            if st and not st['active']: raise HTTPException(403,'Management account is disabled')
        except HTTPException: raise
        except Exception: pass
    return u
def public_user(u):
    if not u:return None
    d=dict(u)
    for k in ('password_hash','email','phone'):
        d.pop(k,None)
    return d

def private_user(u):
    if not u:return None
    d=dict(u); d.pop('password_hash',None); return d

class Register(BaseModel): name:str=Field(min_length=2,max_length=100); email:Optional[EmailStr]=None; phone:Optional[str]=None; password:str=Field(min_length=8,max_length=128); type:str='farmer'; location:Optional[str]=None; division:Optional[str]=None; district:Optional[str]=None; upazila:Optional[str]=None; union_name:Optional[str]=None; area_name:Optional[str]=None
class Login(BaseModel): identifier:str; password:str
class RoleLogin(BaseModel): identifier:str; password:str; role_slug:str
class StaffCreate(BaseModel): name:str=Field(min_length=2,max_length=100); email:Optional[EmailStr]=None; phone:Optional[str]=None; password:str=Field(min_length=8,max_length=128); role_slug:str; verified:bool=True
class RoleAssignment(BaseModel): user_id:str; role_slug:str; primary:bool=True
class RolePermissionsUpdate(BaseModel): permissions:list[str]=[]
class StaffStatusUpdate(BaseModel): active:bool
class StaffPasswordReset(BaseModel): password:str=Field(min_length=8,max_length=128)
class ProfileUpdate(BaseModel): name:Optional[str]=None; avatar:Optional[str]=None; cover:Optional[str]=None; location:Optional[str]=None; division:Optional[str]=None; district:Optional[str]=None; upazila:Optional[str]=None; union_name:Optional[str]=None; area_name:Optional[str]=None; bio:Optional[str]=None; email:Optional[EmailStr]=None; phone:Optional[str]=None
class PostIn(BaseModel): text:str=Field(min_length=1,max_length=5000); images:list[str]=[]; videos:list[str]=[]
class PostUpdate(BaseModel): text:str=Field(min_length=1,max_length=5000); images:list[str]=[]; videos:list[str]=[]
class DeviceTokenIn(BaseModel): token:str=Field(min_length=8,max_length=5000); platform:Optional[str]=None
class CallEventIn(BaseModel): event:str=Field(min_length=1,max_length=50)
class CommentIn(BaseModel): text:str=Field(min_length=1,max_length=2000)
class ProductIn(BaseModel): name:str; price:float=Field(gt=0); unit:str='piece'; category:Optional[str]=None; stock:float=Field(default=0,ge=0); location:Optional[str]=None; description:Optional[str]=None; tags:list[str]=[]; images:list[str]=[]
class SellerPageIn(BaseModel): page_name:str=Field(min_length=2,max_length=120); description:Optional[str]=''; logo:Optional[str]=None; cover:Optional[str]=None; phone:Optional[str]=None; location:Optional[str]=None
class SellerAreaIn(BaseModel): division:Optional[str]=None; district:Optional[str]=None; upazila:Optional[str]=None; union_name:Optional[str]=None; area_name:Optional[str]=None; radius_km:Optional[float]=Field(default=None,ge=0)
class SellerSubscribeIn(BaseModel): plan_id:str
class DeliveryTrackingIn(BaseModel): carrier:Optional[str]=None; tracking_number:Optional[str]=None; status:str='pending'; proof_url:Optional[str]=None

class SellerAdIn(BaseModel): product_id:Optional[str]=None; headline:str=Field(min_length=2,max_length=160); description:Optional[str]=''; image:Optional[str]=None; landing_url:Optional[str]=None; area_id:Optional[str]=None; starts_at:Optional[str]=None; ends_at:Optional[str]=None
class CartIn(BaseModel): product_id:str; quantity:float=Field(gt=0)
class Checkout(BaseModel): delivery_address:str=Field(min_length=5)
class MessageIn(BaseModel): text:Optional[str]=None; attachment_url:Optional[str]=None
class ReportIn(BaseModel): target_type:str; target_id:str; reason:str
class PasswordChange(BaseModel): current_password:str; new_password:str=Field(min_length=8,max_length=128)
class AdminUserUpdate(BaseModel): type:Optional[str]=None; verified:Optional[bool]=None
class RatingIn(BaseModel): rating:int=Field(ge=1,le=5); comment:Optional[str]=None
class KnowledgeIn(BaseModel): title:str=Field(min_length=2,max_length=200); content:str=Field(min_length=10); source:Optional[str]=None
class PriceIn(BaseModel): crop:str; market:Optional[str]=None; price:float=Field(gt=0); unit:str='kg'; date:Optional[str]=None; source:Optional[str]=None

def audit(u,action,entity_type=None,entity_id=None,request=None,metadata=None):
    try:
        ip=request.client.host if request and request.client else None
        q('INSERT INTO audit_logs VALUES(?,?,?,?,?,?,?,?)',(uid('aud'),u.get('id') if u else None,action,entity_type,entity_id,ip,json.dumps(metadata or {},ensure_ascii=False),now()))
    except Exception as e: logger.warning('audit failed: %s',e)



class CropCategoryIn(BaseModel):
    name_bn:str=Field(min_length=2,max_length=100); name_en:Optional[str]=None; slug:str=Field(min_length=2,max_length=100); sort_order:int=0; active:bool=True
class CropIn(BaseModel):
    category_id:str; name_bn:str=Field(min_length=2,max_length=120); name_en:Optional[str]=None; slug:str=Field(min_length=2,max_length=120); scientific_name:Optional[str]=None; description:Optional[str]=None; perennial:bool=False; active:bool=True
class CropVarietyIn(BaseModel):
    crop_id:str; name_bn:str=Field(min_length=2,max_length=120); name_en:Optional[str]=None; season:Optional[str]=None; days_to_harvest:Optional[int]=None; min_temp:Optional[float]=None; max_temp:Optional[float]=None; notes:Optional[str]=None; active:bool=True
class CropRegionIn(BaseModel):
    name_bn:str=Field(min_length=2,max_length=100); name_en:Optional[str]=None; code:Optional[str]=None; description:Optional[str]=None; active:bool=True
class LifecycleIn(BaseModel):
    crop_id:str; variety_id:Optional[str]=None; stage_name_bn:str=Field(min_length=2,max_length=120); stage_name_en:Optional[str]=None; age_start_day:Optional[int]=None; age_end_day:Optional[int]=None; stage_order:int=0; season:Optional[str]=None; description:Optional[str]=None; active:bool=True
class ManagementRuleIn(BaseModel):
    crop_id:str; variety_id:Optional[str]=None; stage_id:Optional[str]=None; region_id:Optional[str]=None; season:Optional[str]=None; age_start_day:Optional[int]=None; age_end_day:Optional[int]=None; management_type:str; title_bn:str; instructions_bn:str; quantity_json:Optional[dict]=None; conditions_json:Optional[dict]=None; priority:int=0; source:Optional[str]=None; verified_at:Optional[str]=None; status:str='draft'
class PestIn(BaseModel):
    crop_id:str; name_bn:str; name_en:Optional[str]=None; scientific_name:Optional[str]=None; symptoms:Optional[str]=None; early_warning:Optional[str]=None; prevention:Optional[str]=None; monitoring:Optional[str]=None; source:Optional[str]=None; status:str='draft'
class DiseaseIn(BaseModel):
    crop_id:str; name_bn:str; name_en:Optional[str]=None; pathogen:Optional[str]=None; symptoms:Optional[str]=None; visual_signs:Optional[str]=None; early_warning:Optional[str]=None; prevention:Optional[str]=None; source:Optional[str]=None; status:str='draft'
class ProblemActionIn(BaseModel):
    crop_id:str; pest_id:Optional[str]=None; disease_id:Optional[str]=None; stage_id:Optional[str]=None; region_id:Optional[str]=None; season:Optional[str]=None; action_type:str; title_bn:str; action_bn:str; urgency:str='normal'; source:Optional[str]=None; verified_at:Optional[str]=None; status:str='draft'
class TreatmentIn(BaseModel):
    crop_id:str; pest_id:Optional[str]=None; disease_id:Optional[str]=None; product_name_bn:Optional[str]=None; active_ingredient:Optional[str]=None; formulation:Optional[str]=None; registered_crop:Optional[str]=None; target_name:Optional[str]=None; dose_text:Optional[str]=None; application_method:Optional[str]=None; phi_days:Optional[int]=None; safety_text:Optional[str]=None; registration_no:Optional[str]=None; source:Optional[str]=None; last_verified_at:Optional[str]=None; status:str='draft'
class CropMediaIn(BaseModel):
    crop_id:str; pest_id:Optional[str]=None; disease_id:Optional[str]=None; media_type:str; url:str; caption_bn:Optional[str]=None; stage_id:Optional[str]=None; source:Optional[str]=None; verified_at:Optional[str]=None; status:str='draft'
class NotificationRuleIn(BaseModel):
    crop_id:str; variety_id:Optional[str]=None; stage_id:Optional[str]=None; region_id:Optional[str]=None; season:Optional[str]=None; age_start_day:Optional[int]=None; age_end_day:Optional[int]=None; trigger_type:str; title_bn:str; message_template_bn:str; days_before:int=0; priority:int=0; enabled:bool=True; source:Optional[str]=None; status:str='draft'
class FarmerCropProfileIn(BaseModel):
    crop_id:str; variety_id:Optional[str]=None; region_id:Optional[str]=None; season:Optional[str]=None; planting_date:str; area_value:Optional[float]=None; area_unit:str='decimal'; notes:Optional[str]=None

def _json(v): return json.dumps(v or {},ensure_ascii=False)
def _crop_admin(u): return u if u['type'] in ('admin','super_admin') else (_ for _ in ()).throw(HTTPException(403,'Admin access required'))
def _insert_crop(table, fields, values, prefix='ci'):
    cid=uid(prefix); ts=now(); cols=['id']+fields+['created_at','updated_at'] if 'updated_at' in fields else None


class FarmIn(BaseModel):
    name:str='আমার খামার'; total_area_value:float=0; total_area_unit:str='decimal'; soil_type:Optional[str]=None; water_source:Optional[str]=None; location:Optional[str]=None; division:Optional[str]=None; district:Optional[str]=None; upazila:Optional[str]=None; union_name:Optional[str]=None; area_name:Optional[str]=None
class PlotIn(BaseModel):
    farm_id:Optional[str]=None; name:str=Field(min_length=1,max_length=120); area_value:float=Field(gt=0); area_unit:str='decimal'; land_type:Optional[str]=None; soil_type:Optional[str]=None; water_source:Optional[str]=None; location:Optional[str]=None; tenure:Optional[str]=None
class FarmJournalIn(BaseModel):
    text:str=Field(min_length=1,max_length=5000); source_type:str='text'

_UNIT_TO_DECIMAL={'decimal':1.0,'shotok':1.0,'শতক':1.0,'শতাংশ':1.0,'katha':1.65,'কাঠা':1.65,'bigha':33.0,'বিঘা':33.0,'acre':100.0,'একর':100.0,'hectare':247.105,'হেক্টর':247.105}
def _area_decimal(value,unit):
    u=(unit or 'decimal').strip().lower(); return round(float(value)*_UNIT_TO_DECIMAL.get(u,1.0),4)
def _norm_tokens(text): return re.findall(r'[\w\u0980-\u09FF\d.\-]+', (text or '').lower())
def _find_active_farm(u):
    f=q('SELECT * FROM farmer_farms WHERE user_id=? AND status=? ORDER BY created_at LIMIT 1',(u['id'],'active'),True)
    if f:return f
    fid=uid('farm'); ts=now(); q('INSERT INTO farmer_farms(id,user_id,name,created_at,updated_at) VALUES(?,?,?,?,?)',(fid,u['id'],'আমার খামার',ts,ts)); return q('SELECT * FROM farmer_farms WHERE id=?',(fid,),True)
def _match_plot(user_id, phrase=''):
    rows=q('SELECT p.*,f.user_id FROM farm_plots p JOIN farmer_farms f ON f.id=p.farm_id WHERE f.user_id=? AND p.active=1 ORDER BY p.created_at',(user_id,))
    if not rows:return None
    phrase=(phrase or '').lower().strip()
    if not phrase:return rows[0] if len(rows)==1 else None
    scored=[]
    for r in rows:
        blob=' '.join(str(r.get(k) or '') for k in ('name','land_type','soil_type','location','tenure')).lower()
        score=sum(1 for t in _norm_tokens(phrase) if len(t)>1 and t in blob)
        scored.append((score,r))
    scored.sort(key=lambda x:x[0],reverse=True)
    return scored[0][1] if scored and scored[0][0]>0 else None

def _match_crop(plot_id, phrase=''):
    rows=q('SELECT * FROM plot_crops WHERE plot_id=? AND status=? ORDER BY created_at DESC',(plot_id,'active'))
    if not rows:return None
    phrase=(phrase or '').lower()
    for r in rows:
        blob=' '.join(str(r.get(k) or '') for k in ('crop_name','variety_name')).lower()
        if any(t in blob for t in _norm_tokens(phrase) if len(t)>1): return r
    return rows[0] if len(rows)==1 else None

def _extract_number_unit(text):
    m=re.search(r'(\d+(?:\.\d+)?)\s*(বিঘা|কাঠা|শতক|শতাংশ|একর|হেক্টর|bigha|katha|decimal|shotok|acre|hectare)',text,re.I)
    return (float(m.group(1)),m.group(2)) if m else (None,None)

def _parse_journal_fallback(text):
    t=text.strip(); low=t.lower(); result={'intent':'activity','confidence':0.55,'activities':[],'inputs':[],'land_changes':[],'unresolved':[]}
    area_pairs=re.findall(r'(\d+(?:\.\d+)?)\s*(বিঘা|কাঠা|শতক|শতাংশ|একর|হেক্টর|bigha|katha|decimal|shotok|acre|hectare)',t,re.I)
    if any(k in low for k in ['ছেড়ে','ছেড়ে','বর্গা ছেড়ে','বর্গা ছেড়ে','নিলাম','নিয়ে নিলাম','নিলেন']):
        result['intent']='land_change'
        if len(area_pairs)>=2:
            (ov,ou),(nv,nu)=area_pairs[0],area_pairs[1]
            result['land_changes'].append({'action':'replace','old_area_value':float(ov),'old_area_unit':ou,'new_area_value':float(nv),'new_area_unit':nu,'reason':t})
            result['confidence']=0.78
    crop=None; variety=None
    patterns=[r'(?:লাগালাম|লাগালেন|রোপণ করলাম|রোপণ করেছি|বুনলাম|বপন করলাম)\s*([^।,]+)',r'(?:চাষ করছি|চাষ করলাম|চাষ করেছি)\s*([^।,]+)']
    for pat in patterns:
        m=re.search(pat,t)
        if m:
            chunk=m.group(1).strip(); crop=chunk; break
    if 'মরিচ' in t: crop='মরিচ'
    if 'ধান' in t: crop='ধান'
    if 'লাউ' in t: crop='লাউ'
    vm=re.search(r'(?:জাত|জাতের)?\s*([\w\u0980-\u09FF\d-]{2,})\s*(?:জাত)?\s*(?:মরিচ|ধান|লাউ)?',t)
    for candidate in ['ডিজি ১৭১৭','ডিজি-১৭১৭','ব্রি-৮৯','ব্রি ৮৯']:
        if candidate in t: variety=candidate; break
    if crop:
        result['activities'].append({'activity_type':'planting','crop_name':crop,'variety_name':variety,'details':t,'activity_date':'today'})
        result['confidence']=max(result['confidence'],0.72)
    for kw,typ in [('সার','fertilizer'),('ইউরিয়া','fertilizer'),('ইউরিয়া','fertilizer'),('টিএসপি','fertilizer'),('এমওপি','fertilizer'),('ওষুধ','pesticide'),('কীটনাশক','pesticide'),('ছত্রাকনাশক','fungicide'),('সেচ','irrigation')]:
        if kw in t:
            result['inputs'].append({'input_type':typ,'input_name':kw,'details':t,'application_date':'today'})
    if any(k in t for k in ['পোকা','রোগ','ঝলসা','পাতা হলুদ','মরে যাচ্ছে']):
        result['activities'].append({'activity_type':'problem_report','details':t,'activity_date':'today'})
        result['confidence']=max(result['confidence'],0.68)
    if not result['activities'] and not result['inputs'] and not result['land_changes']:
        result['unresolved'].append('কথাটির নির্দিষ্ট কৃষি কাজ শনাক্ত করা যায়নি')
    return result

def _ai_parse_journal(text, context):
    if not os.getenv('OPENAI_API_KEY','').strip(): return None
    instructions="""তুমি Krishok Connect-এর Farm Journal data extraction engine। কৃষকের স্বাভাবিক বাংলা কথাকে শুধু structured JSON-এ রূপান্তর করবে। কোনো তথ্য বানাবে না। বিদ্যমান plot/crop/variety নামের সঙ্গে মিল থাকলে সেই নাম ব্যবহার করবে। date না থাকলে today লিখবে। land change হলে পুরোনো জমি বন্ধ এবং নতুন জমি যোগ/পরিবর্তনের intent দেবে। fertilizer/pesticide-এর পরিমাণ না বলা থাকলে null রাখবে। JSON keys: intent, confidence, activities[], inputs[], land_changes[], unresolved[]. activities fields: activity_type,crop_name,variety_name,plot_hint,activity_date,details. inputs: input_type,input_name,quantity_value,quantity_unit,plot_hint,application_date,notes. land_changes: action,old_plot_hint,old_area_value,old_area_unit,new_plot_name,new_area_value,new_area_unit,tenure,reason,effective_date."""
    payload={'model':os.getenv('OPENAI_MODEL','gpt-5.6-luna'),'store':False,'instructions':instructions,'input':'Existing farmer context:\n'+json.dumps(context,ensure_ascii=False)+'\nFarmer message:\n'+text}
    try:
        raw=_openai_responses(payload,timeout=60)
        if not raw:return None
        m=re.search(r'\{.*\}',raw,re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as e:
        logger.warning('journal AI parse failed: %s',e); return None

def _apply_journal(u, journal_id, parsed):
    farm=_find_active_farm(u); changes=[]; created=[]
    for ch in parsed.get('land_changes',[]) or []:
        oldp=_match_plot(u['id'],ch.get('old_plot_hint') or '')
        if oldp:
            ts=now(); q('UPDATE farm_plots SET active=0,closed_at=?,close_reason=?,updated_at=? WHERE id=?',(ch.get('effective_date') or ts, ch.get('reason') or 'farmer journal update',ts,oldp['id']))
            q('INSERT INTO farm_area_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid('fah'),u['id'],oldp['farm_id'],oldp['id'],'close',oldp['area_value'],oldp['area_unit'],oldp['area_decimal'],0,'decimal',0,ch.get('reason'),ch.get('effective_date') or ts,journal_id,ts))
            changes.append({'action':'closed_plot','plot_id':oldp['id'],'name':oldp['name']})
            q('INSERT INTO farm_events VALUES(?,?,?,?,?,?,?,?,?)',(uid('fev'),u['id'],oldp['farm_id'],oldp['id'],None,'plot_closed',ch.get('effective_date') or ts,json.dumps(ch,ensure_ascii=False),journal_id,ts))
        nv=ch.get('new_area_value')
        if nv:
            nu=ch.get('new_area_unit') or 'decimal'; name=ch.get('new_plot_name') or 'নতুন জমি'; ts=now(); pid=uid('plot')
            q('INSERT INTO farm_plots(id,farm_id,name,area_value,area_unit,area_decimal,tenure,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,farm['id'],name,float(nv),nu,_area_decimal(nv,nu),ch.get('tenure'),1,ts,ts))
            q('INSERT INTO farm_area_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid('fah'),u['id'],farm['id'],pid,'add',0,'decimal',0,float(nv),nu,_area_decimal(nv,nu),ch.get('reason'),ch.get('effective_date') or ts,journal_id,ts))
            changes.append({'action':'added_plot','plot_id':pid,'name':name,'area_value':nv,'area_unit':nu})
            q('INSERT INTO farm_events VALUES(?,?,?,?,?,?,?,?,?)',(uid('fev'),u['id'],farm['id'],pid,None,'plot_added',ch.get('effective_date') or ts,json.dumps(ch,ensure_ascii=False),journal_id,ts))
    for a in parsed.get('activities',[]) or []:
        plot=_match_plot(u['id'],a.get('plot_hint') or '')
        crop=_match_crop(plot['id'],a.get('crop_name') or '') if plot else None
        ci=None
        if a.get('activity_type')=='planting' and plot and a.get('crop_name'):
            ts=now(); ciid=uid('pc'); ci=ciid
            cat_crop=q('SELECT id FROM crops WHERE active=1 AND (LOWER(name_bn)=LOWER(?) OR LOWER(name_en)=LOWER(?)) LIMIT 1',(a['crop_name'],a['crop_name']),True)
            variety_row=q('SELECT id FROM crop_varieties WHERE active=1 AND crop_id=? AND LOWER(name_bn)=LOWER(?) LIMIT 1',(cat_crop['id'],a.get('variety_name')) ,True) if cat_crop and a.get('variety_name') else None
            q('INSERT INTO plot_crops(id,plot_id,crop_id,variety_id,crop_name,variety_name,planting_date,area_value,area_unit,area_decimal,season,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ciid,plot['id'],cat_crop['id'] if cat_crop else None,variety_row['id'] if variety_row else None,a['crop_name'],a.get('variety_name'),a.get('activity_date') if a.get('activity_date')!='today' else ts[:10],plot['area_value'],plot['area_unit'],plot['area_decimal'],None,'active',a.get('details'),ts,ts))
        ts=now(); q('INSERT INTO farm_activity_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid('far'),u['id'],plot['id'] if plot else None,ci or (crop['id'] if crop else None),a.get('activity_type') or 'activity',a.get('activity_date') if a.get('activity_date')!='today' else ts[:10],a.get('details') or '',a.get('quantity_value'),a.get('quantity_unit'),journal_id,float(parsed.get('confidence',0.5)),1 if a.get('needs_confirmation') else 0,ts)); created.append({'type':'activity','plot_id':plot['id'] if plot else None,'crop_instance_id':ci})
    for x in parsed.get('inputs',[]) or []:
        plot=_match_plot(u['id'],x.get('plot_hint') or '')
        crop=_match_crop(plot['id'],'') if plot else None; ts=now()
        q('INSERT INTO farm_input_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid('fin'),u['id'],plot['id'] if plot else None,crop['id'] if crop else None,x.get('input_type') or 'other',x.get('input_name') or 'অজানা',x.get('quantity_value'),x.get('quantity_unit'),x.get('application_date') if x.get('application_date')!='today' else ts[:10],x.get('notes') or x.get('details') or '',journal_id,float(parsed.get('confidence',0.5)),ts)); created.append({'type':'input','plot_id':plot['id'] if plot else None})
        q('INSERT INTO farm_events VALUES(?,?,?,?,?,?,?,?,?)',(uid('fev'),u['id'],farm['id'],plot['id'] if plot else None,crop['id'] if crop else None,'input',x.get('application_date') if x.get('application_date')!='today' else ts[:10],json.dumps(x,ensure_ascii=False),journal_id,ts))
    # Keep the farm summary synchronized with active plots; history remains immutable.
    total=sum(float(r.get('area_decimal') or 0) for r in q('SELECT area_decimal FROM farm_plots WHERE farm_id=? AND active=1',(farm['id'],)))
    q('UPDATE farmer_farms SET total_area_value=?,total_area_unit=?,updated_at=? WHERE id=? AND user_id=?',(total,'decimal',now(),farm['id'],u['id']))
    farm=q('SELECT * FROM farmer_farms WHERE id=?',(farm['id'],),True)
    return {'farm':farm,'changes':changes,'created':created}

@app.get('/api/v1/farmer/ai-context')
def farmer_ai_context(u=Depends(me)):
    farm=_find_active_farm(u)
    plots=q('SELECT * FROM farm_plots WHERE farm_id=? AND active=1 ORDER BY created_at',(farm['id'],))
    out=[]
    for p in plots:
        crops=q('SELECT * FROM plot_crops WHERE plot_id=? AND status=? ORDER BY planting_date DESC',(p['id'],'active'))
        acts=q('SELECT * FROM farm_activity_records WHERE plot_id=? ORDER BY activity_date DESC,created_at DESC LIMIT 20',(p['id'],))
        ins=q('SELECT * FROM farm_input_records WHERE plot_id=? ORDER BY application_date DESC,created_at DESC LIMIT 20',(p['id'],))
        out.append({'plot':p,'crops':crops,'recent_activities':acts,'recent_inputs':ins})
    return {'farm':farm,'plots':out}

@app.get('/api/v1/farmer/farm')
def get_farmer_farm(u=Depends(me)):
    farm=_find_active_farm(u); plots=q('SELECT * FROM farm_plots WHERE farm_id=? ORDER BY active DESC,created_at',(farm['id'],)); crops=[]
    for p in plots: crops.extend(q('SELECT * FROM plot_crops WHERE plot_id=? AND status=? ORDER BY planting_date DESC',(p['id'],'active')))
    return {'farm':farm,'plots':plots,'crops':crops}

@app.post('/api/v1/farmer/farm')
def create_farmer_farm(x:FarmIn,u=Depends(me)):
    fid=uid('farm'); ts=now(); q('INSERT INTO farmer_farms(id,user_id,name,total_area_value,total_area_unit,soil_type,water_source,location,division,district,upazila,union_name,area_name,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,u['id'],x.name,x.total_area_value,x.total_area_unit,x.soil_type,x.water_source,x.location,x.division,x.district,x.upazila,x.union_name,x.area_name,'active',ts,ts)); return q('SELECT * FROM farmer_farms WHERE id=?',(fid,),True)

@app.post('/api/v1/farmer/farm/plots')
def create_farmer_plot(x:PlotIn,u=Depends(me)):
    farm=q('SELECT * FROM farmer_farms WHERE id=? AND user_id=? AND status=?',(x.farm_id,u['id'],'active'),True) if x.farm_id else _find_active_farm(u)
    if not farm: raise HTTPException(404,'Farm not found')
    pid=uid('plot'); ts=now(); q('INSERT INTO farm_plots(id,farm_id,name,area_value,area_unit,area_decimal,land_type,soil_type,water_source,location,tenure,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,farm['id'],x.name,x.area_value,x.area_unit,_area_decimal(x.area_value,x.area_unit),x.land_type,x.soil_type,x.water_source,x.location,x.tenure,1,ts,ts)); return q('SELECT * FROM farm_plots WHERE id=?',(pid,),True)

@app.get('/api/v1/farmer/farm/journal')
def farmer_journal(limit:int=50,u=Depends(me)):
    return q('SELECT * FROM farm_journal_entries WHERE user_id=? ORDER BY created_at DESC LIMIT ?',(u['id'],max(1,min(limit,200))))

@app.post('/api/v1/farmer/farm/journal')
def farmer_journal(x:FarmJournalIn,u=Depends(me)):
    jid=uid('fj'); ts=now(); q('INSERT INTO farm_journal_entries(id,user_id,entry_text,source_type,parse_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(jid,u['id'],x.text,x.source_type if x.source_type in ('text','voice_transcript') else 'text','pending',ts,ts))
    farm=get_farmer_farm(u); context={'plots':farm['plots'],'active_crops':farm['crops']}
    parsed=_ai_parse_journal(x.text,context) or _parse_journal_fallback(x.text)
    # normalize today and confidence
    parsed['confidence']=float(parsed.get('confidence') or 0.5)
    result=_apply_journal(u,jid,parsed)
    needs=bool(parsed.get('unresolved')) or parsed['confidence']<0.60
    q('UPDATE farm_journal_entries SET parsed_json=?,parse_status=?,needs_confirmation=?,updated_at=? WHERE id=? AND user_id=?',(json.dumps(parsed,ensure_ascii=False), 'needs_confirmation' if needs else 'applied',1 if needs else 0,now(),jid,u['id']))
    return {'journal_id':jid,'text':x.text,'parsed':parsed,'applied':result,'needs_confirmation':needs}

@app.post('/api/v1/farmer/farm/journal/{journal_id}/reprocess')
def reprocess_farmer_journal(journal_id:str,x:FarmJournalIn,u=Depends(me)):
    row=q('SELECT * FROM farm_journal_entries WHERE id=? AND user_id=?',(journal_id,u['id']),True)
    if not row: raise HTTPException(404,'Journal entry not found')
    farm=get_farmer_farm(u); context={'plots':farm['plots'],'active_crops':farm['crops']}
    parsed=_ai_parse_journal(x.text,context) or _parse_journal_fallback(x.text); parsed['confidence']=float(parsed.get('confidence') or 0.5)
    # Reprocessing creates a new journal version; existing records are never destructively rewritten.
    jid=uid('fj'); ts=now(); q('INSERT INTO farm_journal_entries(id,user_id,entry_text,source_type,parse_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(jid,u['id'],x.text,x.source_type if x.source_type in ('text','voice_transcript') else 'text','pending',ts,ts))
    result=_apply_journal(u,jid,parsed); needs=bool(parsed.get('unresolved')) or parsed['confidence']<0.60
    q('UPDATE farm_journal_entries SET parsed_json=?,parse_status=?,needs_confirmation=?,updated_at=? WHERE id=?',(json.dumps(parsed,ensure_ascii=False),'needs_confirmation' if needs else 'applied',1 if needs else 0,now(),jid))
    return {'journal_id':jid,'parsed':parsed,'applied':result,'needs_confirmation':needs,'replaces_journal_id':journal_id}

@app.get('/api/v1/farmer/farm/activities')
def farmer_activities(limit:int=100,u=Depends(me)):
    return q('SELECT * FROM farm_activity_records WHERE user_id=? ORDER BY activity_date DESC,created_at DESC LIMIT ?',(u['id'],max(1,min(limit,300))))

@app.get('/api/v1/farmer/farm/inputs')
def farmer_inputs(limit:int=100,u=Depends(me)):
    return q('SELECT * FROM farm_input_records WHERE user_id=? ORDER BY application_date DESC,created_at DESC LIMIT ?',(u['id'],max(1,min(limit,300))))

@app.get('/api/v1/crops/catalog')
def crop_catalog(category:Optional[str]=None, active:bool=True):
    cats=q('SELECT * FROM crop_categories WHERE active=? ORDER BY sort_order,name_bn',(1 if active else 0,))
    out=[]
    for c in cats:
        if category and c['slug']!=category and c['id']!=category: continue
        crops=q('SELECT * FROM crops WHERE category_id=? AND active=? ORDER BY name_bn',(c['id'],1 if active else 0))
        out.append({**c,'crops':crops})
    return out

@app.get('/api/v1/crops/{crop_id}/intelligence')
def crop_intelligence(crop_id:str, age_day:Optional[int]=None, stage_id:Optional[str]=None, region_id:Optional[str]=None, season:Optional[str]=None, variety_id:Optional[str]=None, soil_type:Optional[str]=None, weather_context:Optional[str]=None):
    crop=q('SELECT * FROM crops WHERE id=?',(crop_id,),True)
    if not crop: raise HTTPException(404,'Crop not found')
    params=[crop_id]; where='crop_id=? AND status=?'; params.append('approved')
    stages=q('SELECT * FROM crop_lifecycle_stages WHERE crop_id=? AND active=1 ORDER BY stage_order,age_start_day',(crop_id,))
    if age_day is not None:
        stages=[x for x in stages if (x.get('age_start_day') is None or age_day>=x['age_start_day']) and (x.get('age_end_day') is None or age_day<=x['age_end_day'])]
    rules=q('SELECT * FROM crop_management_rules WHERE '+where+' ORDER BY priority DESC,age_start_day',(tuple(params)))
    def match(r): return (not variety_id or r.get('variety_id') in (None,variety_id)) and (age_day is None or (r.get('age_start_day') is None or age_day>=r['age_start_day']) and (r.get('age_end_day') is None or age_day<=r['age_end_day'])) and (not stage_id or r.get('stage_id') in (None,stage_id)) and (not region_id or r.get('region_id') in (None,region_id)) and (not season or r.get('season') in (None,season))
    rules=[r for r in rules if match(r)]
    pests=q('SELECT * FROM crop_pests WHERE crop_id=? AND status=? ORDER BY name_bn',(crop_id,'approved'))
    diseases=q('SELECT * FROM crop_diseases WHERE crop_id=? AND status=? ORDER BY name_bn',(crop_id,'approved'))
    treatments=q('SELECT * FROM crop_treatments WHERE crop_id=? AND status=? ORDER BY last_verified_at DESC',(crop_id,'approved'))
    return {'crop':crop,'stages':stages,'management_rules':rules,'pests':pests,'diseases':diseases,'treatments':treatments,'context':{'variety_id':variety_id,'soil_type':soil_type,'weather_context':weather_context}}

@app.get('/api/v1/crops/{crop_id}/schedule')
def crop_schedule(crop_id:str, age_day:int, region_id:Optional[str]=None, season:Optional[str]=None):
    data=crop_intelligence(crop_id,age_day=age_day,region_id=region_id,season=season)
    return {'crop':data['crop'],'age_day':age_day,'stage':data['stages'][0] if data['stages'] else None,'actions':data['management_rules']}

@app.get('/api/v1/crops/{crop_id}/notifications')
def crop_notification_preview(crop_id:str, age_day:int, region_id:Optional[str]=None, season:Optional[str]=None):
    rows=q('SELECT * FROM crop_notification_rules WHERE crop_id=? AND enabled=1 AND status=? ORDER BY priority DESC',(crop_id,'approved'))
    def ok(r): return (r.get('age_start_day') is None or age_day>=r['age_start_day']) and (r.get('age_end_day') is None or age_day<=r['age_end_day']) and (not region_id or r.get('region_id') in (None,region_id)) and (not season or r.get('season') in (None,season))
    return [r for r in rows if ok(r)]

@app.post('/api/v1/farmer/crops')
def farmer_crop_profile(x:FarmerCropProfileIn,u=Depends(me)):
    # Compatibility adapter: all new crop records are stored in Farm → Plot → Crop.
    if u['type']!='farmer': raise HTTPException(403,'Farmer only')
    crop=q('SELECT * FROM crops WHERE id=? AND active=1',(x.crop_id,),True)
    if not crop: raise HTTPException(404,'Crop not found')
    farm=_find_active_farm(u)
    plot=q('SELECT * FROM farm_plots WHERE farm_id=? AND active=1 ORDER BY created_at LIMIT 1',(farm['id'],),True)
    if not plot:
        ts=now(); pid=uid('plot')
        area=float(x.area_value or 0); unit=x.area_unit or 'decimal'
        q('INSERT INTO farm_plots(id,farm_id,name,area_value,area_unit,area_decimal,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(pid,farm['id'],'আমার জমি',area,unit,_area_decimal(area,unit),1,ts,ts))
        plot=q('SELECT * FROM farm_plots WHERE id=?',(pid,),True)
    variety=q('SELECT * FROM crop_varieties WHERE id=? AND crop_id=? AND active=1',(x.variety_id,x.crop_id),True) if x.variety_id else None
    ts=now(); cid=uid('pc')
    q('INSERT INTO plot_crops(id,plot_id,crop_id,variety_id,crop_name,variety_name,planting_date,area_value,area_unit,area_decimal,season,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,plot['id'],crop['id'],variety['id'] if variety else None,crop['name_bn'],variety['name_bn'] if variety else None,x.planting_date,x.area_value or plot['area_value'],x.area_unit or plot['area_unit'],_area_decimal(x.area_value or plot['area_value'],x.area_unit or plot['area_unit']),x.season,'active',x.notes,ts,ts))
    q('UPDATE farmer_farms SET updated_at=? WHERE id=?',(ts,farm['id']))
    return q('SELECT * FROM plot_crops WHERE id=?',(cid,),True)

@app.get('/api/v1/farmer/crops')
def farmer_crop_profiles(u=Depends(me)):
    if u['type']!='farmer': raise HTTPException(403,'Farmer only')
    return q("SELECT pc.id,pc.crop_id,pc.variety_id,pc.crop_name AS crop_name_bn,pc.variety_name,pc.planting_date,pc.area_value,pc.area_unit,pc.notes,pc.status,fp.name AS plot_name FROM plot_crops pc JOIN farm_plots fp ON fp.id=pc.plot_id JOIN farmer_farms ff ON ff.id=fp.farm_id WHERE ff.user_id=? AND pc.status='active' ORDER BY pc.planting_date DESC,pc.created_at DESC",(u['id'],))

@app.patch('/api/v1/farmer/crops/{profile_id}')
def update_farmer_crop(profile_id:str,x:FarmerCropProfileIn,u=Depends(me)):
    row=q('SELECT pc.* FROM plot_crops pc JOIN farm_plots fp ON fp.id=pc.plot_id JOIN farmer_farms ff ON ff.id=fp.farm_id WHERE pc.id=? AND ff.user_id=? AND pc.status=?',(profile_id,u['id'],'active'),True)
    if not row: raise HTTPException(404,'Crop profile not found')
    crop=q('SELECT * FROM crops WHERE id=? AND active=1',(x.crop_id,),True)
    if not crop: raise HTTPException(404,'Crop not found')
    variety=q('SELECT * FROM crop_varieties WHERE id=? AND crop_id=? AND active=1',(x.variety_id,x.crop_id),True) if x.variety_id else None
    ts=now(); q('UPDATE plot_crops SET crop_id=?,variety_id=?,crop_name=?,variety_name=?,planting_date=?,area_value=?,area_unit=?,area_decimal=?,season=?,notes=?,updated_at=? WHERE id=?',(x.crop_id,variety['id'] if variety else None,crop['name_bn'],variety['name_bn'] if variety else None,x.planting_date,x.area_value,x.area_unit,_area_decimal(x.area_value or 0,x.area_unit),x.season,x.notes,ts,profile_id))
    return q('SELECT * FROM plot_crops WHERE id=?',(profile_id,),True)

@app.delete('/api/v1/farmer/crops/{profile_id}')
def delete_farmer_crop(profile_id:str,u=Depends(me)):
    row=q('SELECT pc.* FROM plot_crops pc JOIN farm_plots fp ON fp.id=pc.plot_id JOIN farmer_farms ff ON ff.id=fp.farm_id WHERE pc.id=? AND ff.user_id=? AND pc.status=?',(profile_id,u['id'],'active'),True)
    if not row: raise HTTPException(404,'Crop profile not found')
    # Never destroy farm history; mark the crop closed.
    ts=now(); q("UPDATE plot_crops SET status='archived',harvest_date=COALESCE(harvest_date,?),updated_at=? WHERE id=?",(ts[:10],ts,profile_id))
    return {'ok':True,'archived':True}

def _migrate_legacy_crop_profiles():
    # One-time compatibility migration from the old farmer_crop_profiles model.
    try:
        rows=q("SELECT * FROM farmer_crop_profiles WHERE status='active'")
        for r in rows:
            exists=q('SELECT id FROM plot_crops WHERE id=?',(r['id'],),True)
            if exists: continue
            farm=_find_active_farm(q('SELECT * FROM users WHERE id=?',(r['user_id'],),True))
            if not farm: continue
            plot=q('SELECT * FROM farm_plots WHERE farm_id=? AND active=1 ORDER BY created_at LIMIT 1',(farm['id'],),True)
            if not plot:
                ts=now(); pid=uid('plot'); area=float(r.get('area_value') or 0); unit=r.get('area_unit') or 'decimal'
                q('INSERT INTO farm_plots(id,farm_id,name,area_value,area_unit,area_decimal,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(pid,farm['id'],'আমার জমি',area,unit,_area_decimal(area,unit),1,ts,ts)); plot=q('SELECT * FROM farm_plots WHERE id=?',(pid,),True)
            crop=q('SELECT * FROM crops WHERE id=?',(r['crop_id'],),True); variety=q('SELECT * FROM crop_varieties WHERE id=?',(r.get('variety_id'),),True) if r.get('variety_id') else None
            if not crop: continue
            ts=now(); q('INSERT INTO plot_crops(id,plot_id,crop_id,variety_id,crop_name,variety_name,planting_date,area_value,area_unit,area_decimal,season,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(r['id'],plot['id'],crop['id'],variety['id'] if variety else None,crop['name_bn'],variety['name_bn'] if variety else None,r['planting_date'],r.get('area_value') or plot['area_value'],r.get('area_unit') or plot['area_unit'],_area_decimal(r.get('area_value') or plot['area_value'],r.get('area_unit') or plot['area_unit']),r.get('season'),'active',r.get('notes'),ts,ts))
    except Exception as e:
        logger.warning('legacy crop migration skipped: %s',e)
_migrate_legacy_crop_profiles()

@app.get('/api/v1/admin/crop-intelligence/summary')
def crop_admin_summary(u=Depends(knowledge_admin)):
    tables=['crop_categories','crops','crop_varieties','crop_regions','crop_lifecycle_stages','crop_management_rules','crop_pests','crop_diseases','crop_problem_actions','crop_treatments','crop_media','crop_notification_rules']
    return {t:q('SELECT COUNT(*) AS count FROM '+t,(),True)['count'] for t in tables}

# Generic admin CRUD endpoints keep the data model extensible without replacing existing AI ingestion/diagnosis APIs.
def _crud(table, model, prefix, u):
    if 'crop.create' not in permission_codes(u): raise HTTPException(403,'Crop data create permission required')
    data=model.model_dump(); cid=uid(prefix); ts=now(); data['created_at']=ts; data['updated_at']=ts; data['id']=cid
    cols=list(data.keys()); vals=[data[k] if not isinstance(data[k],(dict,list)) else _json(data[k]) for k in cols]
    q('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join(['?']*len(cols))+')',tuple(vals)); audit(u,'crop_intelligence.create',table,cid); return q('SELECT * FROM '+table+' WHERE id=?',(cid,),True)

@app.post('/api/v1/admin/crop-intelligence/categories')
def create_cat(x:CropCategoryIn,u=Depends(knowledge_admin)): return _crud('crop_categories',x,'cat',u)
@app.post('/api/v1/admin/crop-intelligence/crops')
def create_crop(x:CropIn,u=Depends(knowledge_admin)): return _crud('crops',x,'crop',u)
@app.post('/api/v1/admin/crop-intelligence/varieties')
def create_variety(x:CropVarietyIn,u=Depends(knowledge_admin)): return _crud('crop_varieties',x,'var',u)
@app.post('/api/v1/admin/crop-intelligence/regions')
def create_region(x:CropRegionIn,u=Depends(knowledge_admin)): return _crud('crop_regions',x,'reg',u)
@app.post('/api/v1/admin/crop-intelligence/stages')
def create_stage(x:LifecycleIn,u=Depends(knowledge_admin)): return _crud('crop_lifecycle_stages',x,'stage',u)
@app.post('/api/v1/admin/crop-intelligence/management-rules')
def create_rule(x:ManagementRuleIn,u=Depends(knowledge_admin)): return _crud('crop_management_rules',x,'rule',u)
@app.post('/api/v1/admin/crop-intelligence/pests')
def create_pest(x:PestIn,u=Depends(knowledge_admin)): return _crud('crop_pests',x,'pest',u)
@app.post('/api/v1/admin/crop-intelligence/diseases')
def create_disease(x:DiseaseIn,u=Depends(knowledge_admin)): return _crud('crop_diseases',x,'dis',u)
@app.post('/api/v1/admin/crop-intelligence/actions')
def create_action(x:ProblemActionIn,u=Depends(knowledge_admin)): return _crud('crop_problem_actions',x,'act',u)
@app.post('/api/v1/admin/crop-intelligence/treatments')
def create_treatment(x:TreatmentIn,u=Depends(knowledge_admin)): return _crud('crop_treatments',x,'trt',u)
@app.post('/api/v1/admin/crop-intelligence/media')
def create_media(x:CropMediaIn,u=Depends(knowledge_admin)): return _crud('crop_media',x,'med',u)
@app.post('/api/v1/admin/crop-intelligence/notification-rules')
def create_notification_rule(x:NotificationRuleIn,u=Depends(knowledge_admin)): return _crud('crop_notification_rules',x,'nr',u)

@app.get('/api/v1/admin/crop-intelligence/{table}')
def admin_table_list(table:str,limit:int=200,u=Depends(knowledge_admin)):
    allowed={'categories':'crop_categories','crops':'crops','varieties':'crop_varieties','regions':'crop_regions','stages':'crop_lifecycle_stages','management-rules':'crop_management_rules','pests':'crop_pests','diseases':'crop_diseases','actions':'crop_problem_actions','treatments':'crop_treatments','media':'crop_media','notification-rules':'crop_notification_rules'}
    if table not in allowed: raise HTTPException(404,'Unknown crop intelligence table')
    return q('SELECT * FROM '+allowed[table]+' ORDER BY created_at DESC LIMIT ?',(min(limit,500),))


@app.post('/api/v1/admin/crop-intelligence/notifications/generate')
def generate_crop_notifications(u=Depends(knowledge_admin)):
    profiles=q("SELECT * FROM farmer_crop_profiles WHERE status='active'")
    created=0
    for p in profiles:
        try:
            planted=datetime.fromisoformat(p['planting_date'].replace('Z','+00:00'))
        except Exception:
            try: planted=datetime.fromisoformat(p['planting_date'])
            except Exception: continue
        if planted.tzinfo is None: planted=planted.replace(tzinfo=timezone.utc)
        age=max(0,(datetime.now(timezone.utc)-planted).days)
        rules=q('SELECT * FROM crop_notification_rules WHERE crop_id=? AND enabled=1 AND status=? ORDER BY priority DESC',(p['crop_id'],'approved'))
        for r in rules:
            if r.get('variety_id') and r['variety_id']!=p.get('variety_id'): continue
            if r.get('region_id') and r['region_id']!=p.get('region_id'): continue
            if r.get('season') and r['season']!=p.get('season'): continue
            if r.get('age_start_day') is not None and age<r['age_start_day']: continue
            if r.get('age_end_day') is not None and age>r['age_end_day']: continue
            scheduled=(datetime.now(timezone.utc)+timedelta(days=max(0,r.get('days_before') or 0))).date().isoformat()
            exists=q('SELECT id FROM crop_notification_log WHERE profile_id=? AND rule_id=? AND scheduled_for=?',(p['id'],r['id'],scheduled),True)
            if exists: continue
            msg=(r['message_template_bn'] or '').replace('{age_day}',str(age)).replace('{crop}',str(p['crop_id']))
            q('INSERT INTO crop_notification_log VALUES(?,?,?,?,?,?,?,?)',(uid('cnl'),p['id'],r['id'],scheduled,None,'in_app','pending',msg))
            q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('not'),p['user_id'],msg,'crop_management',0,now()))
            created+=1
    audit(u,'crop.notifications.generate','crop_notification_log',None,metadata={'created':created})
    return {'created':created}

@app.get('/health')
def health():
    db_ok=False
    try: q('SELECT 1',(),True); db_ok=True
    except Exception: pass
    return {'ok':db_ok,'service':'krishok-connect-api','version':'3.0.0-production-hardening','database':'postgresql' if USE_POSTGRES else 'sqlite','time':now()}

@app.get('/ready')
def ready():
    try: q('SELECT 1',(),True); return {'ready':True}
    except Exception as e: raise HTTPException(503,'Database not ready')
@app.post('/api/v1/auth/register')
def register(x:Register):
    if not x.email and not x.phone: raise HTTPException(422,'email or phone is required')
    if x.email and q('SELECT id FROM users WHERE email=?',(str(x.email),),True): raise HTTPException(409,'Email already registered')
    if x.phone and q('SELECT id FROM users WHERE phone=?',(x.phone,),True): raise HTTPException(409,'Phone already registered')
    if x.type not in ('farmer','business','expert'): raise HTTPException(400,'Public registration only supports farmer, business, or expert accounts')
    u={'id':uid(),'name':x.name,'email':str(x.email) if x.email else None,'phone':x.phone,'password_hash':pwd.hash(x.password),'type':x.type,'verified':1,'avatar':None,'cover':None,'location':x.location,'division':x.division,'district':x.district,'upazila':x.upazila,'union_name':x.union_name,'area_name':x.area_name,'bio':None,'created_at':now()}
    q('INSERT INTO users(id,name,email,phone,password_hash,type,location,division,district,upazila,union_name,area_name,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(u[k] for k in ['id','name','email','phone','password_hash','type','location','division','district','upazila','union_name','area_name','created_at']))
    created=q('SELECT * FROM users WHERE id=?',(u['id'],),True)
    return {**auth_payload(created),'verified':True,'verification_required':False,'message':'Account created successfully'}
def auth_payload(u):
    d=public_user(u); d['roles']=role_slugs(u); d['permissions']=permission_codes(u)
    return {'user':d,'access_token':token_for(u),'token_type':'bearer','roles':d['roles'],'permissions':d['permissions']}

def _is_management_role(slug):
    return slug in {'super_admin','admin','crop_admin','content_admin','market_admin','finance_admin','support_admin','moderation_admin'}


@app.post('/api/v1/auth/role-login')
def role_login(x:RoleLogin, request:Request):
    ident=x.identifier.strip().lower()
    ip=request.client.host if request.client else 'unknown'
    _login_guard(ident,ip)
    u=q('SELECT * FROM users WHERE email=? OR phone=?',(ident,ident),True)
    if not u or not pwd.verify(x.password,u['password_hash']):
        _login_failure(ident,ip)
        raise HTTPException(401,'Invalid credentials')
    if not _is_management_role(x.role_slug): raise HTTPException(400,'Management login only')
    if x.role_slug not in role_slugs(u): raise HTTPException(403,'এই account-এর জন্য নির্বাচিত বিভাগ অনুমোদিত নয়')
    st=q('SELECT active,locked_until FROM staff_accounts WHERE user_id=?',(u['id'],),True)
    if st and not st['active']: raise HTTPException(403,'Management account is disabled')
    if st and st.get('locked_until'):
        try:
            if datetime.fromisoformat(st['locked_until']) > datetime.now(timezone.utc): raise HTTPException(423,'Management account temporarily locked')
        except ValueError: pass
    audit(u,'auth.management_login','user',u['id'],metadata={'role':x.role_slug})
    return auth_payload(u)


@app.get('/api/v1/auth/access')
def auth_access(u=Depends(me)):
    return {'user':public_user(u),'roles':role_slugs(u),'permissions':permission_codes(u),'primary_role':(role_slugs(u) or ['farmer'])[0]}

@app.post('/api/v1/super-admin/staff')
def create_staff(x:StaffCreate,u=Depends(require_super_admin)):
    if x.role_slug not in RBAC_ROLES or x.role_slug in ('super_admin','farmer','business','expert'):
        raise HTTPException(400,'এই endpoint-এ operational staff role নির্বাচন করুন')
    if not x.email and not x.phone: raise HTTPException(422,'email or phone is required')
    if x.email and q('SELECT id FROM users WHERE email=?',(str(x.email),),True): raise HTTPException(409,'Email already registered')
    if x.phone and q('SELECT id FROM users WHERE phone=?',(x.phone,),True): raise HTTPException(409,'Phone already registered')
    uidv=uid(); q('INSERT INTO users(id,name,email,phone,password_hash,type,verified,created_at) VALUES(?,?,?,?,?,?,?,?)',(uidv,x.name,str(x.email) if x.email else None,x.phone,pwd.hash(x.password),x.role_slug,int(x.verified),now()))
    role=q('SELECT id FROM roles WHERE slug=?',(x.role_slug,),True)
    q('INSERT INTO user_roles(user_id,role_id,is_primary,created_at) VALUES(?,?,1,?)',(uidv,role['id'],now()))
    audit(u,'rbac.staff.create','user',uidv,metadata={'role':x.role_slug})
    return {'user':public_user(q('SELECT * FROM users WHERE id=?',(uidv,),True)),'roles':[x.role_slug],'permissions':permission_codes(q('SELECT * FROM users WHERE id=?',(uidv,),True))}

@app.get('/api/v1/super-admin/roles')
def list_roles(u=Depends(require_super_admin)):
    rows=q('SELECT r.*,COUNT(rp.permission_id) permission_count FROM roles r LEFT JOIN role_permissions rp ON rp.role_id=r.id GROUP BY r.id ORDER BY r.department,r.slug')
    for r in rows:
        rr=q('SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id WHERE rp.role_id=? ORDER BY p.code',(r['id'],))
        r['permissions']=[x['code'] for x in rr]
    return rows

@app.get('/api/v1/super-admin/permissions')
def list_permissions(u=Depends(require_super_admin)):
    return q('SELECT id,code,name FROM permissions ORDER BY code')

@app.patch('/api/v1/super-admin/roles/{role_slug}/permissions')
def update_role_permissions(role_slug:str,x:RolePermissionsUpdate,u=Depends(require_super_admin)):
    if role_slug not in RBAC_ROLES: raise HTTPException(404,'Role not found')
    if role_slug=='super_admin' and set(x.permissions)!=set(p[0] for p in RBAC_PERMISSIONS):
        raise HTTPException(400,'Super Admin must retain all system permissions')
    valid={r['code'] for r in q('SELECT code FROM permissions')}
    invalid=set(x.permissions)-valid
    if invalid: raise HTTPException(422,'Unknown permissions: '+', '.join(sorted(invalid)))
    forbidden=set(x.permissions)-allowed_permissions_for_role(role_slug)
    if forbidden: raise HTTPException(403, 'Department isolation prevents these permissions: ' + ', '.join(sorted(forbidden)))
    role=q('SELECT id FROM roles WHERE slug=?',(role_slug,),True)
    if not role: raise HTTPException(404,'Role not found')
    q('DELETE FROM role_permissions WHERE role_id=?',(role['id'],))
    for code in sorted(set(x.permissions)):
        perm=q('SELECT id FROM permissions WHERE code=?',(code,),True)
        q('INSERT INTO role_permissions(role_id,permission_id) VALUES(?,?)',(role['id'],perm['id']))
    audit(u,'rbac.role.permissions.update','role',role['id'],metadata={'role':role_slug,'permissions':sorted(set(x.permissions))})
    return {'role':role_slug,'permissions':sorted(set(x.permissions))}

@app.post('/api/v1/super-admin/role-assignments')
def assign_role(x:RoleAssignment,u=Depends(require_super_admin)):
    target=q('SELECT * FROM users WHERE id=?',(x.user_id,),True)
    if not target: raise HTTPException(404,'User not found')
    if x.role_slug not in RBAC_ROLES: raise HTTPException(400,'Invalid role')
    if x.role_slug not in ('super_admin','admin','farmer','business','expert'):
        existing=[r for r in role_slugs(target) if r in ('crop_admin','content_admin','market_admin','finance_admin','support_admin','moderation_admin')]
        if existing and x.role_slug not in existing:
            raise HTTPException(409,'একজন Staff-এর জন্য একাধিক operational department role দেওয়া যাবে না')
    role=q('SELECT id FROM roles WHERE slug=?',(x.role_slug,),True)
    if not role: raise HTTPException(404,'Role not found')
    if x.primary: q('UPDATE user_roles SET is_primary=0 WHERE user_id=?',(x.user_id,))
    try: q('INSERT INTO user_roles(user_id,role_id,is_primary,created_at) VALUES(?,?,?,?)',(x.user_id,role['id'],int(x.primary),now()))
    except Exception: q('UPDATE user_roles SET is_primary=? WHERE user_id=? AND role_id=?',(int(x.primary),x.user_id,role['id']))
    audit(u,'rbac.role.assign','user',x.user_id,metadata={'role':x.role_slug,'primary':x.primary})
    return {'user_id':x.user_id,'roles':role_slugs(target),'permissions':permission_codes(target)}

@app.get('/api/v1/super-admin/staff')
def list_staff(u=Depends(require_super_admin)):
    rows=q("SELECT u.*,COALESCE(sa.active,1) AS staff_active FROM users u LEFT JOIN staff_accounts sa ON sa.user_id=u.id WHERE u.type IN ('admin','super_admin','crop_admin','content_admin','market_admin','finance_admin','support_admin','moderation_admin') ORDER BY u.created_at DESC")
    for r in rows: r['roles']=role_slugs(r); r['permissions']=permission_codes(r); r['active']=bool(r.pop('staff_active',1)); r.pop('password_hash',None)
    return rows

@app.patch('/api/v1/super-admin/staff/{user_id}/status')
def update_staff_status(user_id:str,x:StaffStatusUpdate,u=Depends(require_super_admin)):
    target=q('SELECT * FROM users WHERE id=?',(user_id,),True)
    if not target or not _is_management_role(target.get('type','')): raise HTTPException(404,'Management staff not found')
    if target['id']==u['id'] and not x.active: raise HTTPException(400,'You cannot disable your own Super Admin account')
    q('UPDATE staff_accounts SET active=?,updated_at=? WHERE user_id=?',(int(x.active),now(),user_id))
    if not x.active: q('DELETE FROM sessions WHERE user_id=?',(user_id,))
    audit(u,'rbac.staff.status','user',user_id,metadata={'active':x.active})
    return {'user_id':user_id,'active':x.active}

@app.post('/api/v1/super-admin/staff/{user_id}/reset-password')
def reset_staff_password(user_id:str,x:StaffPasswordReset,u=Depends(require_super_admin)):
    target=q('SELECT * FROM users WHERE id=?',(user_id,),True)
    if not target or not _is_management_role(target.get('type','')): raise HTTPException(404,'Management staff not found')
    q('UPDATE users SET password_hash=? WHERE id=?',(pwd.hash(x.password),user_id))
    q('DELETE FROM sessions WHERE user_id=?',(user_id,))
    audit(u,'rbac.staff.password_reset','user',user_id)
    return {'ok':True}

@app.delete('/api/v1/super-admin/staff/{user_id}/roles/{role_slug}')
def remove_staff_role(user_id:str,role_slug:str,u=Depends(require_super_admin)):
    if role_slug=='super_admin': raise HTTPException(400,'Super Admin role cannot be removed here')
    target=q('SELECT * FROM users WHERE id=?',(user_id,),True)
    role=q('SELECT id FROM roles WHERE slug=?',(role_slug,),True)
    if not target or not role: raise HTTPException(404,'User or role not found')
    q('DELETE FROM user_roles WHERE user_id=? AND role_id=?',(user_id,role['id']))
    audit(u,'rbac.role.remove','user',user_id,metadata={'role':role_slug})
    return {'user_id':user_id,'roles':role_slugs(target),'permissions':permission_codes(target)}


LOGIN_MAX_FAILURES = int(os.getenv('LOGIN_MAX_FAILURES','5'))
LOGIN_LOCK_MINUTES = int(os.getenv('LOGIN_LOCK_MINUTES','15'))

def _login_guard(identifier:str, ip:str):
    key_id = identifier.strip().lower()
    row=q('SELECT * FROM auth_login_attempts WHERE identifier=? AND ip=?',(key_id,ip),True)
    if not row: return
    locked=row.get('locked_until')
    if locked:
        try:
            if datetime.fromisoformat(locked) > datetime.now(timezone.utc):
                raise HTTPException(429,'Too many failed login attempts. Try again later.')
        except ValueError:
            pass
    # Expire stale failure windows after one hour.
    if row.get('first_failed_at'):
        try:
            if datetime.now(timezone.utc)-datetime.fromisoformat(row['first_failed_at']) > timedelta(hours=1):
                q('DELETE FROM auth_login_attempts WHERE identifier=? AND ip=?',(key_id,ip))
        except ValueError:
            pass

def _login_failure(identifier:str, ip:str):
    key_id=identifier.strip().lower()
    row=q('SELECT * FROM auth_login_attempts WHERE identifier=? AND ip=?',(key_id,ip),True)
    now_s=now()
    if not row:
        q('INSERT INTO auth_login_attempts(id,identifier,ip,failed_count,first_failed_at,locked_until,updated_at) VALUES(?,?,?,?,?,?,?)',
          (uid('la'),key_id,ip,1,now_s,None,now_s))
        return
    count=int(row.get('failed_count') or 0)+1
    locked_until=None
    if count >= LOGIN_MAX_FAILURES:
        locked_until=(datetime.now(timezone.utc)+timedelta(minutes=LOGIN_LOCK_MINUTES)).isoformat()
    q('UPDATE auth_login_attempts SET failed_count=?,locked_until=?,updated_at=? WHERE id=?',
      (count,locked_until,now_s,row['id']))

def _login_success(identifier:str, ip:str):
    q('DELETE FROM auth_login_attempts WHERE identifier=? AND ip=?',(identifier.strip().lower(),ip))

def _safe_profile_url(value):
    if value is None: return None
    v=str(value).strip()
    if not v: return None
    if any(ord(c)<32 for c in v) or any(c in v for c in ['"', "'", '<', '>', '`']):
        raise HTTPException(422,'Invalid media URL')
    if v.startswith('/media/'): return v
    if re.match(r'^https://[^\\s]+$',v,re.I): return v
    raise HTTPException(422,'Avatar/cover must be an /media/ path or HTTPS URL')

def _safe_url_list(values):
    if values is None: return []
    return [_safe_profile_url(v) for v in values]

def _safe_web_url(value):
    if value is None: return None
    v=str(value).strip()
    if not v: return None
    if any(ord(c)<32 for c in v) or any(c in v for c in ['"', "'", '<', '>', '`']):
        raise HTTPException(422,'Invalid URL')
    if re.match(r'^https://[^\\s]+$',v,re.I) or v.startswith('/'):
        return v
    raise HTTPException(422,'URL must use HTTPS or an internal path')

@app.post('/api/v1/auth/login')
def login(x:Login, request:Request):
    identifier=x.identifier.strip().lower()
    ip=request.client.host if request.client else 'unknown'
    _login_guard(identifier,ip)
    u=q('SELECT * FROM users WHERE email=? OR phone=?',(identifier,identifier),True)
    if not u or not pwd.verify(x.password,u['password_hash']):
        _login_failure(identifier,ip)
        raise HTTPException(401,'Invalid credentials')
    _login_success(identifier,ip)
    return auth_payload(u)
@app.get('/api/v1/auth/me')
def auth_me(u=Depends(me)): return public_user(u)
@app.post('/api/v1/auth/logout')
def logout(authorization:Optional[str]=Header(None),u=Depends(me)):
    try:
        p=jwt.decode(authorization.split(' ',1)[1],SECRET,algorithms=[ALG]); q('DELETE FROM sessions WHERE token_id=?',(p.get('sid'),))
    except: pass
    return {'ok':True}






@app.get('/api/v1/users/me/location')
def get_my_location(u=Depends(me)):
    return {k:u.get(k) for k in ('location','division','district','upazila','union_name','area_name')}

@app.put('/api/v1/users/me/location')
def set_my_location(x:ProfileUpdate,u=Depends(me)):
    data={k:v for k,v in x.model_dump().items() if k in ('location','division','district','upazila','union_name','area_name') and v is not None}
    if data:
        q('UPDATE users SET '+','.join(k+'=?' for k in data)+' WHERE id=?',tuple(data.values())+(u['id'],))
    return {k:q('SELECT '+k+' FROM users WHERE id=?',(u['id'],),True).get(k) for k in ('location','division','district','upazila','union_name','area_name')}

@app.get('/api/v1/users')
def users(search:Optional[str]=None,limit:int=30,offset:int=0,u=Depends(me)):
    if search: rows=q('SELECT * FROM users WHERE name LIKE ? OR location LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?',('%'+search+'%','%'+search+'%',limit,offset))
    else: rows=q('SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?',(limit,offset))
    return [public_user(x) for x in rows]
@app.get('/api/v1/users/{user_id}')
def get_user(user_id:str,u=Depends(me)):
    x=q('SELECT * FROM users WHERE id=?',(user_id,),True)
    if not x: raise HTTPException(404,'User not found')
    x=public_user(x); x['following_by_me']=bool(q('SELECT 1 FROM follows WHERE follower_id=? AND following_id=?',(u['id'],user_id),True)); return x
@app.patch('/api/v1/users/me')
def update_profile(x:ProfileUpdate,u=Depends(me)):
    data=x.model_dump(exclude_none=True)
    for media_field in ('avatar','cover'):
        if media_field in data:
            data[media_field]=_safe_profile_url(data[media_field])
    if 'email' in data: data['email']=str(data['email'])
    if data.get('email') and q('SELECT id FROM users WHERE email=? AND id<>?',(data['email'],u['id']),True): raise HTTPException(409,'Email already registered')
    if data.get('phone') and q('SELECT id FROM users WHERE phone=? AND id<>?',(data['phone'],u['id']),True): raise HTTPException(409,'Phone already registered')
    if data:
        sets=','.join(k+'=?' for k in data); q('UPDATE users SET '+sets+' WHERE id=?',tuple(data.values())+(u['id'],))
    return public_user(q('SELECT * FROM users WHERE id=?',(u['id'],),True))
@app.post('/api/v1/users/{user_id}/follow')
def follow(user_id:str,u=Depends(me)):
    if user_id==u['id']: raise HTTPException(400,'Cannot follow yourself')
    target=q('SELECT id FROM users WHERE id=?',(user_id,),True)
    if not target: raise HTTPException(404,'User not found')
    existing=q('SELECT 1 FROM follows WHERE follower_id=? AND following_id=?',(u['id'],user_id),True)
    if existing:
        q('DELETE FROM follows WHERE follower_id=? AND following_id=?',(u['id'],user_id)); q('UPDATE users SET followers=MAX(followers-1,0) WHERE id=?',(user_id,)); q('UPDATE users SET following=MAX(following-1,0) WHERE id=?',(u['id'],)); return {'following':False}
    q('INSERT INTO follows VALUES(?,?,?)',(u['id'],user_id,now())); q('UPDATE users SET followers=followers+1 WHERE id=?',(user_id,)); q('UPDATE users SET following=following+1 WHERE id=?',(u['id'],)); q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),user_id,f'{u["name"]} আপনাকে ফলো করেছেন','follow',0,now())); return {'following':True}

@app.get('/api/v1/posts')
def posts(limit:int=20,offset:int=0,u=Depends(me)):
    rows=q('SELECT * FROM posts ORDER BY created_at DESC LIMIT ? OFFSET ?',(limit,offset)); out=[]
    for p in rows:
        p['images']=json.loads(p.get('images') or '[]'); p['videos']=json.loads(p.get('videos') or '[]'); p['liked']=bool(q('SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?',(p['id'],u['id']),True))
        p['user']=public_user(q('SELECT * FROM users WHERE id=?',(p['user_id'],),True)); p['comments']=q('SELECT c.*,u.name,u.avatar FROM comments c JOIN users u ON u.id=c.user_id WHERE c.post_id=? ORDER BY c.created_at',(p['id'],))
        out.append(p)
    return out
@app.post('/api/v1/posts')
def create_post(x:PostIn,u=Depends(me)):
    pid=uid('p'); q('INSERT INTO posts(id,user_id,text,images,videos,likes,shares,created_at) VALUES(?,?,?,?,?,?,?,?)',(pid,u['id'],x.text,json.dumps(_safe_url_list(x.images),ensure_ascii=False),json.dumps(_safe_url_list(x.videos),ensure_ascii=False),0,0,now())); return get_post(pid,u)
@app.get('/api/v1/posts/{post_id}')
def get_post(post_id:str,u=Depends(me)):
    p=q('SELECT * FROM posts WHERE id=?',(post_id,),True)
    if not p: raise HTTPException(404,'Post not found')
    p['images']=json.loads(p.get('images') or '[]'); p['videos']=json.loads(p.get('videos') or '[]'); p['user']=public_user(q('SELECT * FROM users WHERE id=?',(p['user_id'],),True)); p['comments']=q('SELECT c.*,u.name,u.avatar FROM comments c JOIN users u ON u.id=c.user_id WHERE c.post_id=? ORDER BY c.created_at',(post_id,)); return p
@app.post('/api/v1/posts/{post_id}/like')
def like_post(post_id:str,u=Depends(me)):
    p=q('SELECT * FROM posts WHERE id=?',(post_id,),True)
    if not p: raise HTTPException(404,'Post not found')
    exists=q('SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?',(post_id,u['id']),True)
    if exists:
        q('DELETE FROM post_likes WHERE post_id=? AND user_id=?',(post_id,u['id'])); q('UPDATE posts SET likes=MAX(likes-1,0) WHERE id=?',(post_id,)); return {'liked':False}
    q('INSERT INTO post_likes VALUES(?,?,?)',(post_id,u['id'],now())); q('UPDATE posts SET likes=likes+1 WHERE id=?',(post_id,))
    if p['user_id']!=u['id']: q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),p['user_id'],f'{u["name"]} আপনার পোস্টে লাইক দিয়েছেন','like',0,now()))
    return {'liked':True}
@app.post('/api/v1/posts/{post_id}/comments')
def comment(post_id:str,x:CommentIn,u=Depends(me)):
    if not q('SELECT id FROM posts WHERE id=?',(post_id,),True): raise HTTPException(404,'Post not found')
    cid=uid('cm'); q('INSERT INTO comments VALUES(?,?,?,?,?)',(cid,post_id,u['id'],x.text,now())); return q('SELECT c.*,u.name,u.avatar FROM comments c JOIN users u ON u.id=c.user_id WHERE c.id=?',(cid,),True)

@app.patch('/api/v1/posts/{post_id}')
def update_post(post_id:str,x:PostUpdate,u=Depends(me)):
    p=q('SELECT * FROM posts WHERE id=?',(post_id,),True)
    if not p: raise HTTPException(404,'Post not found')
    if p['user_id']!=u['id']: raise HTTPException(403,'Not allowed')
    q('UPDATE posts SET text=?,images=?,videos=? WHERE id=?',(x.text,json.dumps(_safe_url_list(x.images),ensure_ascii=False),json.dumps(_safe_url_list(x.videos),ensure_ascii=False),post_id)); audit(u,'post.update','post',post_id)
    return get_post(post_id,u)

@app.delete('/api/v1/posts/{post_id}')
def delete_post(post_id:str,u=Depends(me)):
    p=q('SELECT * FROM posts WHERE id=?',(post_id,),True)
    if not p: raise HTTPException(404,'Post not found')
    if p['user_id']!=u['id'] and u['type'] not in ('admin','super_admin'): raise HTTPException(403,'Not allowed')
    q('DELETE FROM posts WHERE id=?',(post_id,)); audit(u,'post.delete','post',post_id); return {'ok':True}

@app.post('/api/v1/posts/{post_id}/share')
def share_post(post_id:str,u=Depends(me)):
    p=q('SELECT id,user_id FROM posts WHERE id=?',(post_id,),True)
    if not p: raise HTTPException(404,'Post not found')
    q('UPDATE posts SET shares=shares+1 WHERE id=?',(post_id,)); audit(u,'post.share','post',post_id)
    if p['user_id']!=u['id']: q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),p['user_id'],f'{u["name"]} আপনার পোস্ট শেয়ার করেছেন','share',0,now()))
    return {'ok':True,'shares':q('SELECT shares FROM posts WHERE id=?',(post_id,),True)['shares']}

def _encode_cursor(created_at, row_id):
    return base64.urlsafe_b64encode(f'{created_at}|{row_id}'.encode()).decode().rstrip('=')
def _decode_cursor(cursor):
    try:
        raw=base64.urlsafe_b64decode(cursor+'='*((4-len(cursor)%4)%4)).decode(); return raw.split('|',1)
    except Exception: raise HTTPException(422,'Invalid cursor')
@app.get('/api/v1/products/cursor')
def products_cursor(search:Optional[str]=None,category:Optional[str]=None,limit:int=30,cursor:Optional[str]=None,u=Depends(me)):
    limit=max(1,min(limit,100)); sql='SELECT * FROM products WHERE active=1'; args=[]
    if search:
        term=search.strip().lstrip('#').lower(); like='%'+term+'%'; sql+=' AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ? OR LOWER(tags) LIKE ?)'; args += [like]*4
    if category: sql+=' AND category=?'; args.append(category)
    if cursor:
        created,rid=_decode_cursor(cursor); sql+=' AND (created_at < ? OR (created_at = ? AND id < ?))'; args += [created,created,rid]
    sql+=' ORDER BY created_at DESC,id DESC LIMIT ?'; args.append(limit+1)
    rows=q(sql,args); has_more=len(rows)>limit; rows=rows[:limit]
    for p in rows:
        p['images']=json.loads(p.get('images') or '[]')
        try:p['tags']=json.loads(p.get('tags') or '[]')
        except Exception:p['tags']=[]
        p['seller']=public_user(q('SELECT * FROM users WHERE id=?',(p['seller_id'],),True))
    return {'items':rows,'next_cursor':_encode_cursor(rows[-1]['created_at'],rows[-1]['id']) if has_more and rows else None,'has_more':has_more}

@app.get('/api/v1/products')
def products(search:Optional[str]=None,category:Optional[str]=None,limit:int=30,offset:int=0,u=Depends(me)):
    sql='SELECT * FROM products WHERE active=1'; args=[]
    if search:
        term=search.strip().lstrip('#').lower()
        like='%'+term+'%'
        sql+=' AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ? OR LOWER(tags) LIKE ?)'
        args += [like,like,like,like]
    if category: sql+=' AND category=?'; args.append(category)
    sql+=' ORDER BY created_at DESC LIMIT ? OFFSET ?'; args += [limit,offset]
    rows=q(sql,args)
    for p in rows:
        p['images']=json.loads(p.get('images') or '[]')
        try:p['tags']=json.loads(p.get('tags') or '[]')
        except Exception:p['tags']=[]
        p['seller']=public_user(q('SELECT * FROM users WHERE id=?',(p['seller_id'],),True))
    return rows
@app.get('/api/v1/products/{product_id}')
def product(product_id:str,u=Depends(me)):
    p=q('SELECT * FROM products WHERE id=?',(product_id,),True)
    if not p: raise HTTPException(404,'Product not found')
    p['images']=json.loads(p.get('images') or '[]')
    try:p['tags']=json.loads(p.get('tags') or '[]')
    except Exception:p['tags']=[]
    p['seller']=public_user(q('SELECT * FROM users WHERE id=?',(p['seller_id'],),True)); return p
@app.post('/api/v1/products')
def create_product(x:ProductIn,u=Depends(me)):
    pid=uid('pr'); tags=[t.strip().lstrip('#') for t in x.tags if t and t.strip()]
    q('INSERT INTO products(id,seller_id,name,price,unit,category,stock,location,description,tags,images,rating,rating_count,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,u['id'],x.name,x.price,x.unit,x.category,x.stock,x.location or u.get('location'),x.description,json.dumps(tags,ensure_ascii=False),json.dumps(_safe_url_list(x.images)),0,0,1,now())); return product(pid,u)
@app.patch('/api/v1/products/{product_id}')
def update_product(product_id:str,x:ProductIn,u=Depends(me)):
    p=q('SELECT * FROM products WHERE id=?',(product_id,),True)
    if not p or p['seller_id']!=u['id']: raise HTTPException(403,'Not allowed')
    tags=[t.strip().lstrip('#') for t in x.tags if t and t.strip()]
    q('UPDATE products SET name=?,price=?,unit=?,category=?,stock=?,location=?,description=?,tags=?,images=? WHERE id=?',(x.name,x.price,x.unit,x.category,x.stock,x.location or u.get('location'),x.description,json.dumps(tags,ensure_ascii=False),json.dumps(x.images),product_id)); return product(product_id,u)

@app.get('/api/v1/cart')
def cart(u=Depends(me)):
    rows=q('SELECT c.quantity,p.*,u.name seller_name FROM carts c JOIN products p ON p.id=c.product_id JOIN users u ON u.id=p.seller_id WHERE c.user_id=?',(u['id'],)); total=0
    for x in rows: x['images']=json.loads(x['images']); x['subtotal']=x['quantity']*x['price']; total+=x['subtotal']
    return {'items':rows,'total':total}
@app.post('/api/v1/cart')
def add_cart(x:CartIn,u=Depends(me)):
    p=q('SELECT * FROM products WHERE id=? AND active=1',(x.product_id,),True)
    if not p: raise HTTPException(404,'Product not found')
    if x.quantity>p['stock']: raise HTTPException(400,'Insufficient stock')
    q('INSERT INTO carts(user_id,product_id,quantity) VALUES(?,?,?) ON CONFLICT(user_id,product_id) DO UPDATE SET quantity=excluded.quantity',(u['id'],x.product_id,x.quantity)); return cart(u)
@app.delete('/api/v1/cart/{product_id}')
def remove_cart(product_id:str,u=Depends(me)): q('DELETE FROM carts WHERE user_id=? AND product_id=?',(u['id'],product_id)); return cart(u)
@app.post('/api/v1/orders')
def checkout(x:Checkout,u=Depends(me)):
    items=q('SELECT c.*,p.name,p.price,p.stock,p.seller_id FROM carts c JOIN products p ON p.id=c.product_id WHERE c.user_id=?',(u['id'],))
    if not items: raise HTTPException(400,'Cart is empty')
    total=sum(i['quantity']*i['price'] for i in items); oid=uid('ord'); t=now(); c=conn()
    try:
        c.execute('BEGIN') if USE_POSTGRES else c.execute('BEGIN IMMEDIATE')
        for i in items:
            cur=c.execute('UPDATE products SET stock=stock-? WHERE id=? AND active=1 AND stock>=?',(i['quantity'],i['product_id'],i['quantity']))
            if cur.rowcount != 1: raise HTTPException(409,f'Insufficient stock for {i["name"]}')
            balance=c.execute('SELECT stock FROM products WHERE id=?',(i['product_id'],)).fetchone()[0]
            c.execute('INSERT INTO inventory_ledger(id,product_id,change_qty,balance_qty,reason,reference_type,reference_id,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(uid('inv'),i['product_id'],-float(i['quantity']),float(balance),'order reservation','order',oid,u['id'],t))
        c.execute('INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?)',(oid,u['id'],total,'pending','unpaid','cod',x.delivery_address,t,t))
        seller_totals={}
        for i in items:
            c.execute('INSERT INTO order_items VALUES(?,?,?,?,?,?,?)',(uid('oi'),oid,i['product_id'],i['seller_id'],i['quantity'],i['price']))
            seller_totals[i['seller_id']]=seller_totals.get(i['seller_id'],0)+(float(i['quantity'])*float(i['price']))
            c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),i['seller_id'],f'নতুন অর্ডার {oid} এসেছে','order',0,t))
        c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),u['id'],f'অর্ডার {oid} সফলভাবে তৈরি হয়েছে','order',0,t))
        c.execute('DELETE FROM carts WHERE user_id=?',(u['id'],)); c.commit()
    except Exception: c.rollback(); raise
    finally:c.close()
    return q('SELECT * FROM orders WHERE id=?',(oid,),True)
@app.get('/api/v1/orders')
def orders(u=Depends(me)):
    rows=q('SELECT * FROM orders WHERE buyer_id=? ORDER BY created_at DESC',(u['id'],))
    for o in rows:o['items']=q('SELECT oi.*,p.name FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?',(o['id'],))
    return rows
@app.patch('/api/v1/orders/{order_id}/status')
def order_status(order_id:str,status:str=Query(...),u=Depends(me)):
    o=q('SELECT * FROM orders WHERE id=?',(order_id,),True)
    if not o: raise HTTPException(404,'Order not found')
    allowed={'pending','confirmed','processing','shipped','delivered','cancelled'}
    if status not in allowed: raise HTTPException(422,'Invalid status')
    is_admin=u['type'] in ('admin','super_admin')
    is_buyer=o['buyer_id']==u['id']
    seller=bool(q('SELECT 1 FROM order_items WHERE order_id=? AND seller_id=?',(order_id,u['id']),True))
    if not (is_admin or is_buyer or seller): raise HTTPException(403,'Not allowed')
    current=o['status']
    if is_buyer and not is_admin and not seller:
        if status not in ('cancelled','delivered') or current not in ('pending','shipped'):
            raise HTTPException(400,'Buyer can only cancel pending orders or confirm delivery after shipping')
    if seller and not is_admin and not is_buyer:
        transitions={'pending':{'confirmed','cancelled'},'confirmed':{'processing','cancelled'},'processing':{'shipped'},'shipped':{'delivered'}}
        if status not in transitions.get(current,set()): raise HTTPException(400,'Invalid seller status transition')
    q('UPDATE orders SET status=?,updated_at=? WHERE id=?',(status,now(),order_id))
    _record_order_status(order_id,status,u['id'])
    if status!=current:
        q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),o['buyer_id'],f'অর্ডার {order_id}: {status}','order',0,now()))
    return q('SELECT * FROM orders WHERE id=?',(order_id,),True)

@app.post('/api/v1/conversations')
def conversation(user_id:str,u=Depends(me)):
    if not q('SELECT id FROM users WHERE id=?',(user_id,),True): raise HTTPException(404,'User not found')
    row=q('SELECT c.id FROM conversations c JOIN conversation_members a ON a.conversation_id=c.id JOIN conversation_members b ON b.conversation_id=c.id WHERE a.user_id=? AND b.user_id=? GROUP BY c.id HAVING COUNT(*)=2',(u['id'],user_id),True)
    if row:return {'id':row['id']}
    cid=uid('c'); q('INSERT INTO conversations VALUES(?,?)',(cid,now())); q('INSERT INTO conversation_members VALUES(?,?),(?,?)',(cid,u['id'],cid,user_id)); return {'id':cid}
@app.get('/api/v1/conversations')
def conversations(u=Depends(me)):
    rows=q('SELECT c.id,c.created_at FROM conversations c JOIN conversation_members m ON m.conversation_id=c.id WHERE m.user_id=? ORDER BY c.created_at DESC',(u['id'],))
    for r in rows:r['members']=q('SELECT u.id,u.name,u.avatar FROM conversation_members m JOIN users u ON u.id=m.user_id WHERE m.conversation_id=?',(r['id'],))
    return rows
@app.post('/api/v1/conversations/{cid}/read')
def mark_conversation_read(cid:str,u=Depends(me)):
    if not q('SELECT 1 FROM conversation_members WHERE conversation_id=? AND user_id=?',(cid,u['id']),True): raise HTTPException(403,'Not a member')
    ts=now(); q('UPDATE messages SET read_at=? WHERE conversation_id=? AND sender_id<>? AND read_at IS NULL',(ts,cid,u['id']))
    return {'ok':True,'read_at':ts}

@app.get('/api/v1/conversations/{cid}/messages')
def messages(cid:str,limit:int=Query(50,ge=1,le=100),before:Optional[str]=Query(None),u=Depends(me)):
    if not q('SELECT 1 FROM conversation_members WHERE conversation_id=? AND user_id=?',(cid,u['id']),True): raise HTTPException(403,'Not a member')
    q('UPDATE messages SET read_at=? WHERE conversation_id=? AND sender_id<>?',(now(),cid,u['id']))
    if before:
        rows=q('SELECT * FROM messages WHERE conversation_id=? AND created_at<? ORDER BY created_at DESC LIMIT ?',(cid,before,limit))
        return list(reversed(rows))
    rows=q('SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT ?',(cid,limit))
    return list(reversed(rows))
@app.post('/api/v1/conversations/{cid}/messages')
def send_message(cid:str,x:MessageIn,u=Depends(me)):
    if not x.text and not x.attachment_url: raise HTTPException(422,'Message is empty')
    if not q('SELECT 1 FROM conversation_members WHERE conversation_id=? AND user_id=?',(cid,u['id']),True): raise HTTPException(403,'Not a member')
    mid=uid('m'); q('INSERT INTO messages(id,conversation_id,sender_id,text,attachment_url,read_at,created_at,delivered_at,edited_at) VALUES(?,?,?,?,?,?,?,?,?)',(mid,cid,u['id'],x.text,_safe_profile_url(x.attachment_url),None,now(),now(),None));
    others=q('SELECT user_id FROM conversation_members WHERE conversation_id=? AND user_id<>?',(cid,u['id']))
    for o in others:q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),o['user_id'],f'{u["name"]} আপনাকে মেসেজ পাঠিয়েছেন','message',0,now()))
    return q('SELECT * FROM messages WHERE id=?',(mid,),True)



def _record_order_status(order_id,status,actor_id=None,note=None):
    q('INSERT INTO order_status_history VALUES(?,?,?,?,?,?)',(uid('osh'),order_id,status,note,actor_id,now()))


@app.get('/api/v1/orders/{order_id}/timeline')
def order_timeline(order_id:str,u=Depends(me)):
    o=q('SELECT * FROM orders WHERE id=?',(order_id,),True)
    if not o: raise HTTPException(404,'Order not found')
    allowed=o['buyer_id']==u['id'] or bool(q('SELECT 1 FROM order_items WHERE order_id=? AND seller_id=?',(order_id,u['id']),True)) or 'orders.manage' in permission_codes(u) or u['type'] in ('admin','super_admin')
    if not allowed: raise HTTPException(403,'Not allowed')
    return q('SELECT * FROM order_status_history WHERE order_id=? ORDER BY created_at',(order_id,))

class ReturnIn(BaseModel): reason:str=Field(min_length=3,max_length=1000); note:Optional[str]=None

@app.post('/api/v1/orders/{order_id}/return')
def request_return(order_id:str,x:ReturnIn,u=Depends(me)):
    o=q('SELECT * FROM orders WHERE id=? AND buyer_id=?',(order_id,u['id']),True)
    if not o: raise HTTPException(404,'Order not found')
    if o['status']!='delivered': raise HTTPException(400,'ডেলিভারির পরই return request করা যাবে')
    if q("SELECT id FROM order_returns WHERE order_id=? AND status IN ('requested','approved','pickup','received','refunding')",(order_id,),True): raise HTTPException(409,'Return request already exists')
    refund=0
    rid=uid('ret'); t=now(); q('INSERT INTO order_returns VALUES(?,?,?,?,?,?,?,?,?)',(rid,order_id,u['id'],x.reason,'requested',refund,x.note,t,t)); q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('n'),u['id'],f'Return request {rid} গ্রহণ করা হয়েছে','return',0,t)); return q('SELECT * FROM order_returns WHERE id=?',(rid,),True)

@app.get('/api/v1/orders/{order_id}/return')
def get_return(order_id:str,u=Depends(me)):
    r=q('SELECT * FROM order_returns WHERE order_id=? ORDER BY created_at DESC LIMIT 1',(order_id,),True)
    if not r: raise HTTPException(404,'Return request not found')
    o=q('SELECT buyer_id FROM orders WHERE id=?',(order_id,),True)
    if not o or (o['buyer_id']!=u['id'] and 'orders.manage' not in permission_codes(u) and u['type'] not in ('admin','super_admin')): raise HTTPException(403,'Not allowed')
    return r

@app.patch('/api/v1/department/market/orders/{order_id}/return')
def manage_return(order_id:str,status:str=Query(...),note:Optional[str]=Query(None),u=Depends(require_department('market_admin'))):
    enforce_work_owner('market_admin','return',order_id,u)
    if status not in ('requested','approved','rejected','pickup','received','refunding','refunded','cancelled'): raise HTTPException(422,'Invalid return status')
    r=q('SELECT * FROM order_returns WHERE order_id=? ORDER BY created_at DESC LIMIT 1',(order_id,),True)
    if not r: raise HTTPException(404,'Return request not found')
    q('UPDATE order_returns SET status=?,note=?,updated_at=? WHERE id=?',(status,note or r.get('note'),now(),r['id']))
    return q('SELECT * FROM order_returns WHERE id=?',(r['id'],),True)




@app.websocket('/ws/conversations/{conversation_id}')
async def websocket_chat(websocket:WebSocket, conversation_id:str, token:str=Query(...)):
    try:
        p=jwt.decode(token,SECRET,algorithms=[ALG]); u=q('SELECT * FROM users WHERE id=?',(p['sub'],),True)
        member=q('SELECT 1 FROM conversation_members WHERE conversation_id=? AND user_id=?',(conversation_id,u['id']),True)
        if not u or not member: await websocket.close(code=4403); return
    except Exception:
        await websocket.close(code=4401); return
    await ws_manager.connect(conversation_id,websocket)
    try:
        while True:
            data=await websocket.receive_json()
            text=(data.get('text') or '').strip(); attachment=data.get('attachment_url')
            if not text and not attachment: continue
            mid=uid('m'); created=now()
            q('INSERT INTO messages(id,conversation_id,sender_id,text,attachment_url,read_at,created_at,delivered_at,edited_at) VALUES(?,?,?,?,?,?,?,?,?)',(mid,conversation_id,u['id'],text or None,attachment,None,created,created,None))
            payload={'id':mid,'conversation_id':conversation_id,'sender_id':u['id'],'text':text or None,'attachment_url':attachment,'created_at':created,'delivered_at':created}
            await ws_manager.broadcast(conversation_id,payload)
    except WebSocketDisconnect:
        ws_manager.disconnect(conversation_id,websocket)
    except Exception:
        ws_manager.disconnect(conversation_id,websocket)




@app.post('/api/v1/farmer/notifications/generate')
def generate_farmer_notifications(u=Depends(me)):
    if u['type']!='farmer': raise HTTPException(403,'Farmer only')
    created=0; farm=_find_active_farm(u)
    rows=q("SELECT pc.*,fp.name plot_name FROM plot_crops pc JOIN farm_plots fp ON fp.id=pc.plot_id JOIN farmer_farms ff ON ff.id=fp.farm_id WHERE ff.user_id=? AND fp.active=1 AND pc.status='active'",(u['id'],))
    for p in rows:
        try: planted=datetime.fromisoformat(str(p['planting_date']).replace('Z','+00:00'))
        except Exception: continue
        if planted.tzinfo is None: planted=planted.replace(tzinfo=timezone.utc)
        age=max(0,(datetime.now(timezone.utc)-planted).days)
        rules=q('SELECT * FROM crop_notification_rules WHERE crop_id=? AND enabled=1 AND status=? ORDER BY priority DESC',(p['crop_id'],'approved'))
        for r in rules:
            if r.get('variety_id') and r['variety_id']!=p.get('variety_id'): continue
            if r.get('season') and r['season']!=p.get('season'): continue
            if r.get('age_start_day') is not None and age<r['age_start_day']: continue
            if r.get('age_end_day') is not None and age>r['age_end_day']: continue
            scheduled=datetime.now(timezone.utc).date().isoformat()
            if q('SELECT id FROM crop_notification_log WHERE profile_id=? AND rule_id=? AND scheduled_for=?',(p['id'],r['id'],scheduled),True): continue
            msg=(r['message_template_bn'] or '').replace('{age_day}',str(age)).replace('{crop}',str(p.get('crop_name') or 'ফসল')).replace('{plot}',str(p.get('plot_name') or 'জমি'))
            q('INSERT INTO crop_notification_log VALUES(?,?,?,?,?,?,?,?)',(uid('cnl'),p['id'],r['id'],scheduled,None,'in_app','pending',msg))
            q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('not'),u['id'],msg,'crop_management',0,now())); created+=1
    return {'created':created}

@app.get('/api/v1/notifications')
def notifications(u=Depends(me),unread_only:bool=False):
    sql='SELECT * FROM notifications WHERE user_id=?'+(' AND read=0' if unread_only else '')+' ORDER BY created_at DESC'; return q(sql,(u['id'],))
@app.post('/api/v1/notifications/{notification_id}/read')
def read_one(notification_id:str,u=Depends(me)):
    q('UPDATE notifications SET read=1 WHERE id=? AND user_id=?',(notification_id,u['id']))
    return {'ok':True}

@app.post('/api/v1/notifications/read-all')
def read_all(u=Depends(me)): q('UPDATE notifications SET read=1 WHERE user_id=?',(u['id'],)); return {'ok':True}
@app.post('/api/v1/reports')
def report(x:ReportIn,u=Depends(me)): rid=uid('r'); q('INSERT INTO reports VALUES(?,?,?,?,?,?,?)',(rid,u['id'],x.target_type,x.target_id,x.reason,'open',now())); return {'id':rid,'status':'open'}

@app.get('/api/v1/market-prices')
def market_prices(crop:Optional[str]=None,market:Optional[str]=None,limit:int=100,u=Depends(me)):
    sql='SELECT * FROM market_prices WHERE 1=1'; args=[]
    if crop:sql+=' AND crop=?';args.append(crop)
    if market:sql+=' AND market=?';args.append(market)
    sql+=' ORDER BY date DESC LIMIT ?';args.append(limit);return q(sql,args)
@app.post('/api/v1/market-prices')
def add_price(x:PriceIn,u=Depends(me)):
    if 'marketplace.manage' not in permission_codes(u) and u['type'] not in ('admin','expert','business','super_admin'): raise HTTPException(403,'Marketplace permission required')
    pid=uid('mp');q('INSERT INTO market_prices VALUES(?,?,?,?,?,?,?)',(pid,x.crop,x.market,x.price,x.unit,x.date or now()[:10],x.source)); audit(u,'market_price.add','market_price',pid); return q('SELECT * FROM market_prices WHERE id=?',(pid,),True)

@app.post('/api/v1/admin/market-prices/sync')
def sync_market_prices(u=Depends(require_admin)):
    url=os.getenv('MARKET_PRICE_URL','').strip()
    if not url: raise HTTPException(503,'MARKET_PRICE_URL is not configured')
    sid=uid('ms'); imported=0
    try:
        req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'KrishokConnect/1.0'})
        with urllib.request.urlopen(req,timeout=15) as r: payload=json.loads(r.read().decode())
        rows=payload.get('prices',payload) if isinstance(payload,(dict,list)) else []
        if isinstance(rows,dict): rows=[rows]
        for x in rows:
            if not x.get('crop') or x.get('price') is None: continue
            q('INSERT INTO market_prices VALUES(?,?,?,?,?,?,?)',(uid('mp'),str(x['crop']),x.get('market'),float(x['price']),x.get('unit','kg'),str(x.get('date') or now()[:10]),x.get('source') or url)); imported+=1
        q('INSERT INTO market_sync_logs VALUES(?,?,?,?,?,?)',(sid,url,'success',imported,None,now())); audit(u,'market.sync','market_sync',sid,metadata={'rows':imported}); return {'ok':True,'rows_imported':imported}
    except Exception as e:
        q('INSERT INTO market_sync_logs VALUES(?,?,?,?,?,?)',(sid,url,'failed',0,str(e)[:500],now())); raise HTTPException(502,'Market price source unavailable')

@app.get('/api/v1/market-prices/trends')
def market_trends(crop:str=Query(...),market:Optional[str]=None,days:int=30,u=Depends(me)):
    args=[crop]; sql='SELECT date,price,unit,market,source FROM market_prices WHERE crop=?'
    if market: sql+=' AND market=?'; args.append(market)
    sql+=' ORDER BY date DESC LIMIT ?'; args.append(max(1,min(days,180)))
    rows=q(sql,args); rows.reverse(); return rows


class AIIn(BaseModel):
    message:str=Field(min_length=1,max_length=4000)
    context:Optional[str]=None

@app.get('/api/v1/notifications/cursor')
def notifications_cursor(limit:int=50,cursor:Optional[str]=None,u=Depends(me)):
    limit=max(1,min(limit,100)); sql='SELECT * FROM notifications WHERE user_id=?'; args=[u['id']]
    if cursor:
        created,rid=_decode_cursor(cursor); sql+=' AND (created_at < ? OR (created_at = ? AND id < ?))'; args += [created,created,rid]
    sql+=' ORDER BY created_at DESC,id DESC LIMIT ?'; args.append(limit+1)
    rows=q(sql,args); has_more=len(rows)>limit; rows=rows[:limit]
    return {'items':rows,'next_cursor':_encode_cursor(rows[-1]['created_at'],rows[-1]['id']) if has_more and rows else None,'has_more':has_more}

@app.get('/api/v1/weather')
def weather(lat:float=Query(...,ge=-90,le=90), lon:float=Query(...,ge=-180,le=180), u=Depends(me)):
    key=f"{lat:.3f},{lon:.3f}"
    cached=q('SELECT * FROM weather_cache WHERE id=?',(key,),True)
    if cached:
        try:
            payload=json.loads(cached['payload'])
            updated=datetime.fromisoformat(cached['updated_at'])
            if datetime.now(timezone.utc)-updated < timedelta(minutes=15): return payload
        except Exception: pass
    params=urllib.parse.urlencode({'latitude':lat,'longitude':lon,'current':'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m','daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max','timezone':'auto','forecast_days':1})
    try:
        with urllib.request.urlopen('https://api.open-meteo.com/v1/forecast?'+params, timeout=8) as r: data=json.loads(r.read().decode())
        payload={'latitude':data.get('latitude'),'longitude':data.get('longitude'),'timezone':data.get('timezone'),'current':data.get('current',{}),'daily':data.get('daily',{}),'source':'Open-Meteo'}
        q('INSERT INTO weather_cache(id,location,payload,updated_at) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',(key,key,json.dumps(payload),now()))
        return payload
    except Exception as e:
        raise HTTPException(503,'আবহাওয়ার তথ্য এখন পাওয়া যাচ্ছে না')

@app.get('/api/v1/weather/advisory')
def weather_advisory(lat:float=Query(...,ge=-90,le=90),lon:float=Query(...,ge=-180,le=180),crop:Optional[str]=None,u=Depends(me)):
    d=weather(lat,lon,u); c=d.get('current',{}); daily=d.get('daily',{})
    rain=(daily.get('precipitation_probability_max') or [0])[0] or 0; temp=c.get('temperature_2m')
    tips=[]
    if rain>=70: tips.append('বৃষ্টির সম্ভাবনা বেশি—সেচ ও স্প্রে করার সময় পুনর্বিবেচনা করুন।')
    if temp is not None and temp>=35: tips.append('তাপমাত্রা বেশি—সকালে/বিকেলে সেচ ও গাছের পানি-চাপ পর্যবেক্ষণ করুন।')
    if temp is not None and temp<=10: tips.append('তাপমাত্রা কম—ঠান্ডাজনিত ক্ষতি হতে পারে এমন ফসল পর্যবেক্ষণ করুন।')
    if not tips: tips.append('আজ আবহাওয়া তুলনামূলক স্বাভাবিক—ফসল নিয়মিত পর্যবেক্ষণ করুন।')
    return {'crop':crop,'tips':tips,'rain_probability':rain,'temperature':temp,'source':d.get('source','Open-Meteo')}

@app.post('/api/v1/media/upload')
async def upload_media(file:UploadFile=File(...),u=Depends(me)):
    allowed={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','video/mp4':'.mp4','video/webm':'.webm','audio/mpeg':'.mp3','audio/wav':'.wav','audio/ogg':'.ogg','audio/mp4':'.m4a'}
    if file.content_type not in allowed: raise HTTPException(415,'এই ফাইল টাইপ অনুমোদিত নয়')
    max_mb=int(os.getenv('MEDIA_MAX_FILE_MB','50' if file.content_type.startswith('video/') else '15'))
    data=await file.read()
    if len(data)>max_mb*1024*1024: raise HTTPException(413,f'ফাইল সর্বোচ্চ {max_mb}MB হতে পারে')
    safe_name=re.sub(r'[^A-Za-z0-9._-]+','_',os.path.basename(file.filename or 'upload'))[:80]
    name=uid('media')+allowed[file.content_type]
    mid=uid('ma'); ts=now(); sha=sha256_bytes(data)
    try:
        media_put(name, data, file.content_type)
    except Exception as e:
        raise HTTPException(503, f'Media storage unavailable: {str(e)[:180]}')
    try:
        q('INSERT INTO media_assets VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,u['id'],name,safe_name,file.content_type,len(data),sha,MEDIA_STORAGE_BACKEND,ts))
    except Exception:
        pass
    audit(u,'media.upload','media',name,metadata={'original_name':safe_name,'size':len(data),'content_type':file.content_type,'sha256':sha})
    return {'url':f'/media/{name}','media_id':mid,'object_key':name,'name':safe_name,'content_type':file.content_type,'size':len(data),'sha256':sha}


def process_ai_ingestion(source_id: str):
    src=q('SELECT * FROM ai_ingestion_sources WHERE id=?',(source_id,),True)
    if not src: return
    try:
        q('UPDATE ai_ingestion_sources SET status=?,updated_at=? WHERE id=?',('processing',now(),source_id))
        parts,kind=extract_file(src['storage_path'])
        q('DELETE FROM ai_ingestion_chunks WHERE source_id=?',(source_id,))
        idx=0; total_chars=0; usable=0
        for part in parts:
            text=(part.get('text') or '').strip()
            if not text: continue
            for ch in chunk_text(text):
                meta=dict(part.get('meta') or {})
                meta.update(part.get('locator') or {})
                q('INSERT INTO ai_ingestion_chunks VALUES(?,?,?,?,?,?,?)',(uid('aic'),source_id,idx,ch,','.join(keywords(ch)),json.dumps(meta,ensure_ascii=False),now()))
                idx+=1; total_chars+=len(ch); usable+=1
        meta=json.loads(src.get('metadata') or '{}') if src.get('metadata') else {}
        meta.update({'chunks':usable,'characters':total_chars,'processor':'krishok-ai-ingestion-v1','kind':kind})
        status='ready_for_review' if usable else 'needs_review'
        q('UPDATE ai_ingestion_sources SET status=?,error=?,metadata=?,updated_at=? WHERE id=?',(status,None if usable else 'কোনো পাঠযোগ্য টেক্সট পাওয়া যায়নি; OCR/ট্রান্সক্রিপশন প্রয়োজন হতে পারে',json.dumps(meta,ensure_ascii=False),now(),source_id))
    except Exception as e:
        logger.exception('AI ingestion failed: %s',e)
        q('UPDATE ai_ingestion_sources SET status=?,error=?,updated_at=? WHERE id=?',('failed',str(e)[:1000],now(),source_id))


class AIKnowledgeMeta(BaseModel):
    title:Optional[str]=None
    category:Optional[str]=None
    crop:Optional[str]=None
    language:Optional[str]='bn'
    notes:Optional[str]=None


def ai_source_public(row):
    if not row: return None
    d=dict(row); d.pop('storage_path',None); return d


@app.post('/api/v1/ai/knowledge/import')
async def ai_knowledge_import(background_tasks: BackgroundTasks, files: list[UploadFile]=File(...), title: Optional[str]=None, u=Depends(knowledge_admin)):
    if not files: raise HTTPException(422,'কমপক্ষে একটি ফাইল দিন')
    if len(files)>30: raise HTTPException(413,'একবারে সর্বোচ্চ ৩০টি ফাইল')
    created=[]
    for upload in files:
        original=os.path.basename(upload.filename or 'upload')
        ext=os.path.splitext(original)[1].lower()
        kind=SUPPORTED.get(ext)
        if not kind: raise HTTPException(415,f'এই ফাইল টাইপ সমর্থিত নয়: {ext or "unknown"}')
        path=os.path.join(AI_INGEST_DIR,uid('src')+ext)
        total=0
        with open(path,'wb') as out:
            while True:
                block=await upload.read(1024*1024)
                if not block: break
                total+=len(block)
                if total>AI_MAX_FILE_MB*1024*1024:
                    out.close();
                    try: os.remove(path)
                    except Exception: pass
                    raise HTTPException(413,f'ফাইল সর্বোচ্চ {AI_MAX_FILE_MB}MB হতে পারে')
                out.write(block)
        digest=sha256_file(path)
        existing=q('SELECT * FROM ai_ingestion_sources WHERE sha256=?',(digest,),True)
        if existing:
            try: os.remove(path)
            except Exception: pass
            created.append(ai_source_public(existing)); continue
        sid=uid('ais'); nowv=now(); meta={'uploaded_mime':upload.content_type,'original_extension':ext}
        q('INSERT INTO ai_ingestion_sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,title or os.path.splitext(original)[0],original,path,upload.content_type,kind,digest,total,'queued',u['id'],None,json.dumps(meta,ensure_ascii=False),nowv,nowv))
        background_tasks.add_task(process_ai_ingestion,sid)
        created.append(ai_source_public(q('SELECT * FROM ai_ingestion_sources WHERE id=?',(sid,),True)))
        audit(u,'ai.ingestion.upload','ai_source',sid,metadata={'name':original,'kind':kind,'size':total})
    return {'count':len(created),'sources':created,'message':'ফাইল গ্রহণ করা হয়েছে; backend processor এখন এগুলো normalize ও chunk করছে।'}


@app.get('/api/v1/ai/knowledge/sources')
def ai_knowledge_sources(status:Optional[str]=None,limit:int=100,u=Depends(knowledge_admin)):
    sql='SELECT * FROM ai_ingestion_sources'; args=[]
    if status: sql+=' WHERE status=?'; args.append(status)
    sql+=' ORDER BY created_at DESC LIMIT ?'; args.append(min(limit,200))
    return [ai_source_public(x) for x in q(sql,args)]


@app.get('/api/v1/ai/knowledge/sources/{source_id}')
def ai_knowledge_source(source_id:str,u=Depends(knowledge_admin)):
    src=q('SELECT * FROM ai_ingestion_sources WHERE id=?',(source_id,),True)
    if not src: raise HTTPException(404,'Knowledge source not found')
    chunks=q('SELECT id,chunk_index,content,keywords,locator,created_at FROM ai_ingestion_chunks WHERE source_id=? ORDER BY chunk_index',(source_id,))
    d=ai_source_public(src); d['chunks']=chunks; return d


@app.post('/api/v1/ai/knowledge/sources/{source_id}/approve')
def approve_ai_knowledge(source_id:str,u=Depends(knowledge_admin)):
    src=q('SELECT * FROM ai_ingestion_sources WHERE id=?',(source_id,),True)
    if not src: raise HTTPException(404,'Knowledge source not found')
    if src['status'] not in ('ready_for_review','approved'): raise HTTPException(409,'Source is not ready for approval')
    existing=q('SELECT id FROM knowledge_documents WHERE source=?',(f'ai-ingestion:{source_id}',),True)
    did=existing['id'] if existing else uid('kd')
    if existing: q('DELETE FROM knowledge_chunks WHERE document_id=?',(did,))
    else: q('INSERT INTO knowledge_documents VALUES(?,?,?,?,?)',(did,src['title'],f'Normalized knowledge from {src["original_name"]}',f'ai-ingestion:{source_id}',now()))
    chunks=q('SELECT * FROM ai_ingestion_chunks WHERE source_id=? ORDER BY chunk_index',(source_id,))
    for ch in chunks: q('INSERT INTO knowledge_chunks VALUES(?,?,?,?,?)',(uid('kc'),did,ch['content'],ch['keywords'],now()))
    q('UPDATE ai_ingestion_sources SET status=?,updated_at=? WHERE id=?',('approved',now(),source_id))
    audit(u,'ai.ingestion.approve','ai_source',source_id,metadata={'chunks':len(chunks)})
    return {'ok':True,'source_id':source_id,'document_id':did,'chunks_promoted':len(chunks)}


@app.post('/api/v1/ai/knowledge/sources/{source_id}/retry')
def retry_ai_knowledge(source_id:str,background_tasks:BackgroundTasks,u=Depends(knowledge_admin)):
    src=q('SELECT * FROM ai_ingestion_sources WHERE id=?',(source_id,),True)
    if not src: raise HTTPException(404,'Knowledge source not found')
    q('UPDATE ai_ingestion_sources SET status=?,error=?,updated_at=? WHERE id=?',('queued',None,now(),source_id))
    background_tasks.add_task(process_ai_ingestion,source_id)
    return {'ok':True,'status':'queued'}


@app.delete('/api/v1/ai/knowledge/sources/{source_id}')
def delete_ai_knowledge(source_id:str,u=Depends(knowledge_admin)):
    src=q('SELECT * FROM ai_ingestion_sources WHERE id=?',(source_id,),True)
    if not src: raise HTTPException(404,'Knowledge source not found')
    doc=q('SELECT id FROM knowledge_documents WHERE source=?',(f'ai-ingestion:{source_id}',),True)
    if doc: q('DELETE FROM knowledge_documents WHERE id=?',(doc['id'],))
    q('DELETE FROM ai_ingestion_sources WHERE id=?',(source_id,))
    try: os.remove(src['storage_path'])
    except Exception: pass
    audit(u,'ai.ingestion.delete','ai_source',source_id)
    return {'ok':True}


@app.post('/api/v1/ai/knowledge')
def add_knowledge(x:KnowledgeIn,u=Depends(knowledge_admin)):
    did=uid('kd'); q('INSERT INTO knowledge_documents VALUES(?,?,?,?,?)',(did,x.title,x.content,x.source,now()))
    words=re.findall(r'[\w\u0980-\u09FF]+',x.content.lower()); chunks=[x.content[i:i+1200] for i in range(0,len(x.content),1000)]
    for ch in chunks: q('INSERT INTO knowledge_chunks VALUES(?,?,?,?,?)',(uid('kc'),did,ch,','.join(sorted(set(words))[:80]),now()))
    return q('SELECT * FROM knowledge_documents WHERE id=?',(did,),True)

def retrieve_knowledge(question,limit=5):
    toks=set(re.findall(r'[\w\u0980-\u09FF]+',question.lower())); rows=q('SELECT * FROM knowledge_chunks ORDER BY created_at DESC LIMIT 500'); scored=[]
    for r in rows:
        kws=set((r.get('keywords') or '').split(',')); score=len(toks & kws)
        if score: scored.append((score,r['content']))
    scored.sort(key=lambda x:x[0],reverse=True); return [x[1] for x in scored[:limit]]

def _openai_responses(payload, timeout=75):
    api_key=os.getenv('OPENAI_API_KEY','').strip()
    if not api_key: return None
    body=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+api_key},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r: data=json.loads(r.read().decode('utf-8'))
    answer=(data.get('output_text') or '').strip()
    if not answer:
        parts=[]
        for item in data.get('output',[]):
            for c in item.get('content',[]) if isinstance(item,dict) else []:
                if isinstance(c,dict) and c.get('type')=='output_text': parts.append(c.get('text') or '')
        answer=''.join(parts).strip()
    return answer or None


def retrieve_diagnosis_knowledge(query, limit=8):
    terms=set(re.findall(r'[\w\u0980-\u09FF]+',(query or '').lower()))
    rows=q('SELECT * FROM knowledge_chunks ORDER BY created_at DESC LIMIT 1200')
    scored=[]
    for r in rows:
        text=(r.get('content') or '')
        kws=set((r.get('keywords') or '').split(','))
        score=len(terms & kws)
        if score: scored.append((score,text))
    scored.sort(key=lambda x:x[0],reverse=True)
    return [x[1] for x in scored[:limit]]


def retrieve_diagnosis_cases(query, crop=None, limit=8):
    rows=q('SELECT * FROM ai_diagnosis_cases ORDER BY updated_at DESC LIMIT 1000')
    terms=set(re.findall(r'[\w\u0980-\u09FF]+',(query or '').lower()))
    scored=[]
    for r in rows:
        blob=' '.join(str(r.get(k) or '') for k in ('title','crop','disease','pest','problem_type','symptoms','visual_signs','causes')).lower()
        score=len(terms & set(re.findall(r'[\w\u0980-\u09FF]+',blob)))
        if crop and str(r.get('crop') or '').lower()==crop.lower(): score+=4
        if score: scored.append((score,r))
    scored.sort(key=lambda x:x[0],reverse=True)
    return [dict(x[1]) for x in scored[:limit]]


def _vision_observe(image_bytes, mime, symptom='', crop=''):
    if not os.getenv('OPENAI_API_KEY','').strip(): return None
    if len(image_bytes)>12*1024*1024: raise HTTPException(413,'ছবির আকার সর্বোচ্চ ১২MB হতে পারে')
    b64=base64.b64encode(image_bytes).decode('ascii')
    prompt=("ছবিটি একটি কৃষি ফসল/গাছের সমস্যার ছবি। শুধু দৃশ্যমান লক্ষণ পর্যবেক্ষণ করো; নিশ্চিত রোগের নাম বানিয়ে বলবে না। "
            "বাংলায় ৬টি অংশ দাও: crop, plant_part, visible_symptoms, color_pattern, pest_or_damage_signs, uncertainty. "
            f"কৃষকের বলা উপসর্গ: {symptom or 'নেই'}; সম্ভাব্য ফসল: {crop or 'অজানা'}")
    payload={'model':os.getenv('OPENAI_VISION_MODEL',os.getenv('OPENAI_MODEL','gpt-5.6-luna')),'store':False,'instructions':'তুমি কৃষি ছবির নিরাপদ visual observation engine। ছবিতে যা দেখা যায় শুধু তাই বলবে; রোগ নিশ্চিত করবে না।','input':[{'role':'user','content':[{'type':'input_text','text':prompt},{'type':'input_image','image_url':f'data:{mime};base64,{b64}'}]}]}
    return _openai_responses(payload)


class DiagnosisCaseIn(BaseModel):
    title:str=Field(min_length=2,max_length=200)
    crop:Optional[str]=None
    disease:Optional[str]=None
    pest:Optional[str]=None
    problem_type:str=Field(min_length=2,max_length=80)
    symptoms:str=Field(min_length=2)
    visual_signs:Optional[str]=None
    causes:Optional[str]=None
    actions:Optional[str]=None
    prevention:Optional[str]=None
    red_flags:Optional[str]=None
    source:Optional[str]=None
    confidence:float=Field(default=0.8,ge=0,le=1)

@app.post('/api/v1/ai/diagnosis/cases')
def add_diagnosis_case(x:DiagnosisCaseIn,u=Depends(knowledge_admin)):
    cid=uid('dc'); ts=now()
    q('INSERT INTO ai_diagnosis_cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,x.title,x.crop,x.disease,x.pest,x.problem_type,x.symptoms,x.visual_signs,x.causes,x.actions,x.prevention,x.red_flags,x.source,x.confidence,ts,ts))
    audit(u,'ai.diagnosis.case_create','diagnosis_case',cid)
    return q('SELECT * FROM ai_diagnosis_cases WHERE id=?',(cid,),True)

@app.get('/api/v1/ai/diagnosis/cases')
def list_diagnosis_cases(limit:int=100,u=Depends(knowledge_admin)):
    return q('SELECT * FROM ai_diagnosis_cases ORDER BY updated_at DESC LIMIT ?',(min(limit,200),))

@app.post('/api/v1/ai/diagnose')
async def ai_diagnose(symptom: str='', crop: str='', age_day: Optional[int]=None, region_id: Optional[str]=None, season: Optional[str]=None, variety_id: Optional[str]=None, soil_type: Optional[str]=None, weather_context: Optional[str]=None, stage_id: Optional[str]=None, image: Optional[UploadFile]=File(None), u=Depends(me)):
    if not symptom.strip() and not crop.strip() and not image:
        raise HTTPException(422,'উপসর্গ, ফসলের নাম অথবা ছবি দিন')
    visual=''
    if image:
        mime=image.content_type or 'image/jpeg'
        if mime not in ('image/jpeg','image/png','image/webp'):
            raise HTTPException(415,'শুধু JPG, PNG বা WEBP ছবি ব্যবহার করুন')
        data=await image.read()
        visual=_vision_observe(data,mime,symptom,crop) or ''
    query=' '.join(x for x in (crop,symptom,visual) if x)
    cases=retrieve_diagnosis_cases(query,crop,8)
    kb=retrieve_diagnosis_knowledge(query,8)
    crop_context={}
    if crop.strip():
        cr=q('SELECT * FROM crops WHERE lower(name_bn)=lower(?) OR lower(name_en)=lower(?) OR lower(slug)=lower(?)',(crop,crop,crop),True)
        if cr:
            crop_context=crop_intelligence(cr['id'],age_day=age_day,region_id=region_id,season=season,variety_id=variety_id,soil_type=soil_type,weather_context=weather_context,stage_id=stage_id)
    if not os.getenv('OPENAI_API_KEY','').strip():
        return {'answer':'ছবি/উপসর্গ বিশ্লেষণের জন্য OpenAI API সংযোগ প্রয়োজন। আপাতত AI চ্যাটে উপসর্গ লিখে দিতে পারেন।','provider':'configuration_required','matched_cases':len(cases),'matched_knowledge':len(kb)}
    instructions="""তুমি Krishok Connect-এর নিরাপদ AI Crop Diagnosis Engine। কৃষকের উপসর্গ ও ছবির দৃশ্যমান লক্ষণ থেকে সম্ভাব্য সমস্যা বিশ্লেষণ করবে। এটি চূড়ান্ত ল্যাব/বিশেষজ্ঞ রোগ নির্ণয় নয়। অনুমোদিত জ্ঞানভান্ডার ও structured cases-কে সর্বোচ্চ গুরুত্ব দেবে। তথ্য না থাকলে স্পষ্ট বলবে।

আউটপুট বাংলায় এই কাঠামোতে দাও:
১) সম্ভাব্য সমস্যা — সর্বোচ্চ ৩টি, সম্ভাব্যতার ক্রমে
২) কেন এমন মনে হচ্ছে — উপসর্গ/ছবির লক্ষণ
৩) এখনই করণীয়
৪) কী করা উচিত নয়
৫) কোন তথ্য/আরও ছবি দিলে নিশ্চিত হওয়া সহজ হবে
৬) জরুরি সতর্কতা
কীটনাশকের নির্দিষ্ট মাত্রা কেবল জ্ঞানভান্ডারে অনুমোদিত তথ্য থাকলে বলবে; না থাকলে পণ্যের লেবেল ও স্থানীয় কৃষি কর্মকর্তার নির্দেশ মানতে বলবে।"""
    instructions += '\n\nকৃষকের উপসর্গ: '+(symptom or 'নেই')+'\nফসল: '+(crop or 'অজানা')+'\nফসলের বয়স: '+(str(age_day) if age_day is not None else 'অজানা')+' দিন\nজাত: '+(variety_id or 'অজানা')+'\nমাটি: '+(soil_type or 'অজানা')+'\nআবহাওয়া: '+(weather_context or 'অজানা')+'\nঅঞ্চল: '+(region_id or 'অজানা')+'\nমৌসুম: '+(season or 'অজানা')+'\nদৃশ্যমান পর্যবেক্ষণ: '+(visual or 'ছবি বিশ্লেষণ করা যায়নি')+'\n\nCrop Intelligence context:\n'+json.dumps(crop_context,ensure_ascii=False)[:24000]+'\n\nঅনুমোদিত structured cases:\n'+json.dumps(cases,ensure_ascii=False)[:18000]+'\n\nঅনুমোদিত knowledge chunks:\n'+'\n---\n'.join(kb)[:18000]
    answer=_openai_responses({'model':os.getenv('OPENAI_MODEL','gpt-5.6-luna'),'store':False,'instructions':instructions,'input':'এই কেসটি বিশ্লেষণ করে নিরাপদ কৃষি পরামর্শ দাও।'},timeout=90)
    if not answer: raise HTTPException(502,'AI diagnosis service did not return an answer')
    audit(u,'ai.diagnosis','ai_case',None,metadata={'has_image':bool(image),'crop':crop})
    return {'answer':answer,'provider':'openai','model':os.getenv('OPENAI_MODEL','gpt-5.6-luna'),'visual_observation':visual,'matched_cases':len(cases),'matched_knowledge':len(kb)}


def _openai_chat(prompt):
    api_key=os.getenv('OPENAI_API_KEY','').strip()
    if not api_key: return None
    model=os.getenv('OPENAI_MODEL','gpt-5.6-luna').strip()
    payload={
        'model':model,
        'store':False,
        'instructions':'তুমি একজন নিরাপদ বাংলা কৃষি সহায়ক। ব্যবহারকারীর ভাষা অনুসরণ করবে; কৃষক বাংলায় প্রশ্ন করলে স্বাভাবিক, পরিষ্কার বাংলায় উত্তর দেবে। রোগ নির্ণয় নিশ্চিত না হলে সম্ভাব্য কারণ বলবে, অতিরিক্ত কীটনাশক ব্যবহার উৎসাহিত করবে না, লেবেলের অনুমোদিত মাত্রা ও স্থানীয় কৃষি কর্মকর্তার পরামর্শ নিতে বলবে। কেবল অনুমোদিত কৃষি জ্ঞানভান্ডারের তথ্যকে প্রামাণ্য জ্ঞান হিসেবে ব্যবহার করবে; জ্ঞানভান্ডারে তথ্য না থাকলে তা স্পষ্ট করবে এবং অনুমানকে নিশ্চিত তথ্য হিসেবে উপস্থাপন করবে না। ইন্টারনেট নিজে থেকে ব্যবহার করবে না।',
        'input':prompt,
    }
    body=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+api_key},method='POST')
    with urllib.request.urlopen(req,timeout=60) as r: data=json.loads(r.read().decode('utf-8'))
    answer=(data.get('output_text') or '').strip()
    if not answer:
        for item in data.get('output',[]):
            for c in item.get('content',[]) if isinstance(item,dict) else []:
                if isinstance(c,dict) and c.get('type')=='output_text': answer+=(c.get('text') or '')
        answer=answer.strip()
    return {'answer':answer,'provider':'openai','model':model} if answer else None

@app.post('/api/v1/ai/chat')
def ai_chat(x:AIIn,u=Depends(me)):
    base=os.getenv('OLLAMA_URL','http://127.0.0.1:11434').rstrip('/')
    model=os.getenv('OLLAMA_MODEL','qwen2.5:3b')
    system='তুমি একজন নিরাপদ বাংলা কৃষি সহায়ক। রোগ নির্ণয় নিশ্চিত না হলে সম্ভাব্য কারণ বলবে, অতিরিক্ত কীটনাশক ব্যবহার উৎসাহিত করবে না, লেবেলের অনুমোদিত মাত্রা ও স্থানীয় কৃষি কর্মকর্তার পরামর্শ নিতে বলবে।'
    kb=retrieve_knowledge(x.message)
    kb_text=('\n'.join(kb)) if kb else ''
    personal=''
    if u.get('type')=='farmer':
        try:
            ctx=farmer_ai_context(u)
            personal='\nব্যক্তিগত কৃষি প্রেক্ষাপট (শুধু এই কৃষকের):\n'+json.dumps(ctx,ensure_ascii=False,default=str)[:30000]
        except Exception as e:
            logger.warning('farmer context unavailable: %s',e)
    prompt=(system+'\n'+('বিশ্বস্ত কৃষি জ্ঞানভান্ডার:\n'+kb_text+'\n' if kb_text else '')+(personal+'\n' if personal else '')+('অতিরিক্ত প্রেক্ষাপট: '+x.context+'\n' if x.context else '')+'কৃষকের প্রশ্ন: '+x.message)

    # OpenAI is the preferred production provider when OPENAI_API_KEY is configured.
    try:
        result=_openai_chat(prompt)
        if result: return result
    except Exception as e:
        logger.warning('OpenAI request failed: %s',e)

    # Local Ollama remains as a no-cost/local fallback.
    body=json.dumps({'model':model,'prompt':prompt,'stream':False}).encode()
    try:
        req=urllib.request.Request(base+'/api/generate',data=body,headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=45) as r: data=json.loads(r.read().decode())
        answer=(data.get('response') or '').strip()
        if answer:return {'answer':answer,'provider':'ollama','model':model}
    except Exception as e:
        logger.warning('Ollama request failed: %s',e)
    lower=x.message.lower(); match=next((k for k in SYMPTOM_FALLBACK if any(key.lower() in lower for key in k['keys'])),None)
    return {'answer':match['reply'] if match else 'এই মুহূর্তে AI সার্ভার সংযোগ পাওয়া যাচ্ছে না। সাধারণ পরামর্শের জন্য রোগ/পোকার নাম লিখে আবার চেষ্টা করুন।','provider':'fallback'}

SYMPTOM_FALLBACK=[
 {'keys':['হলুদ','পাতা হলুদ'],'reply':'পাতা হলুদ হওয়ার কারণ পুষ্টির ঘাটতি, পানি সমস্যা বা পোকার আক্রমণ হতে পারে। জমির অবস্থা ও গাছের অন্যান্য লক্ষণ দেখে সিদ্ধান্ত নিন; মাটি পরীক্ষা করে সুষম সার ব্যবহার করুন।'},
 {'keys':['সাদা মাছি','সাদামাছি'],'reply':'সাদা মাছি হলে হলুদ আঠালো ফাঁদ ব্যবহার করুন, আক্রান্ত অংশ পর্যবেক্ষণ করুন এবং প্রয়োজনে অনুমোদিত বালাইনাশক লেবেল অনুযায়ী ব্যবহার করুন।'},
 {'keys':['মাজরা','কাণ্ড পোকা'],'reply':'মাজরা/কাণ্ড পোকা হলে আক্রান্ত কুশি অপসারণ ও পর্যবেক্ষণ করুন। প্রয়োজনে অনুমোদিত কীটনাশক লেবেলের নির্দেশনা অনুযায়ী ব্যবহার করুন।'},
]

@app.get('/api/v1/rbac/me')
def rbac_me(u=Depends(me)):
    return {'user':public_user(u),'roles':role_slugs(u),'permissions':permission_codes(u),'primary_role':(role_slugs(u) or ['farmer'])[0]}

@app.get('/api/v1/dashboard')
def dashboard(u=Depends(me)):
    return {'user':public_user(u),'stats':{'posts':q('SELECT COUNT(*) n FROM posts WHERE user_id=?',(u['id'],),True)['n'],'products':q('SELECT COUNT(*) n FROM products WHERE seller_id=?',(u['id'],),True)['n'],'orders':q('SELECT COUNT(*) n FROM orders WHERE buyer_id=?',(u['id'],),True)['n'],'unread_notifications':q('SELECT COUNT(*) n FROM notifications WHERE user_id=? AND read=0',(u['id'],),True)['n']}}


# --- Account security and administration ---
@app.post('/api/v1/auth/change-password')
def change_password(x:PasswordChange,u=Depends(me)):
    if not pwd.verify(x.current_password,u['password_hash']): raise HTTPException(400,'বর্তমান পাসওয়ার্ড সঠিক নয়')
    q('UPDATE users SET password_hash=? WHERE id=?',(pwd.hash(x.new_password),u['id']))
    audit(u,'auth.change_password','user',u['id']); return {'ok':True}

@app.delete('/api/v1/auth/account')
def delete_account(u=Depends(me)):
    uid_deleted=u['id']; q('DELETE FROM users WHERE id=?',(uid_deleted,)); audit(u,'auth.delete_account','user',uid_deleted); return {'ok':True}


@app.post('/api/v1/admin/staff/role-assignments')
def admin_assign_staff_role(x:RoleAssignment,u=Depends(require_admin)):
    if 'super_admin' in role_slugs(u):
        # Super Admin uses the canonical endpoint. Keeping this endpoint available
        # for the Admin UI still routes through the same strict role checks.
        pass
    if x.role_slug not in RBAC_ROLES or x.role_slug in ('super_admin','admin','farmer','business','expert'):
        raise HTTPException(403,'Admin can authorize only operational department roles')
    target=q('SELECT * FROM users WHERE id=?',(x.user_id,),True)
    if not target: raise HTTPException(404,'User not found')
    existing=[r for r in role_slugs(target) if r in ('crop_admin','content_admin','market_admin','finance_admin','support_admin','moderation_admin')]
    if existing and x.role_slug not in existing: raise HTTPException(409,'একজন Staff-এর জন্য একাধিক operational department role দেওয়া যাবে না')
    role=q('SELECT id FROM roles WHERE slug=?',(x.role_slug,),True)
    if not role: raise HTTPException(404,'Role not found')
    if x.primary: q('UPDATE user_roles SET is_primary=0 WHERE user_id=?',(x.user_id,))
    try: q('INSERT INTO user_roles(user_id,role_id,is_primary,created_at) VALUES(?,?,?,?)',(x.user_id,role['id'],int(x.primary),now()))
    except Exception: q('UPDATE user_roles SET is_primary=? WHERE user_id=? AND role_id=?',(int(x.primary),x.user_id,role['id']))
    audit(u,'rbac.admin.role.assign','user',x.user_id,metadata={'role':x.role_slug,'primary':x.primary})
    return {'user_id':x.user_id,'roles':role_slugs(target),'permissions':permission_codes(target)}


@app.get('/api/v1/admin/stats')
def admin_stats(u=Depends(require_admin)):
    return {'users':q('SELECT COUNT(*) n FROM users',(),True)['n'],'posts':q('SELECT COUNT(*) n FROM posts',(),True)['n'],'products':q('SELECT COUNT(*) n FROM products',(),True)['n'],'orders':q('SELECT COUNT(*) n FROM orders',(),True)['n'],'open_reports':q("SELECT COUNT(*) n FROM reports WHERE status='open'",(),True)['n']}

@app.get('/api/v1/admin/users')
def admin_users(limit:int=50,offset:int=0,u=Depends(require_admin)):
    return [public_user(x) for x in q('SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?',(limit,offset))]

@app.patch('/api/v1/admin/users/{user_id}')
def admin_update_user(user_id:str,x:AdminUserUpdate,u=Depends(require_admin)):
    target=q('SELECT * FROM users WHERE id=?',(user_id,),True)
    if not target: raise HTTPException(404,'User not found')
    allowed={'farmer','buyer','seller','expert','business','admin','super_admin','crop_admin','content_admin','market_admin','finance_admin','support_admin','moderation_admin'}
    if x.type is not None:
        if x.type not in allowed: raise HTTPException(422,'Invalid user type')
        if target.get('type')=='super_admin' and 'super_admin' not in role_slugs(u):
            raise HTTPException(403,'Only Super Admin can modify a Super Admin')
        if 'super_admin' not in role_slugs(u):
            raise HTTPException(403,'Only Super Admin can change staff role')
    fields=[];args=[]
    if x.type is not None: fields.append('type=?');args.append(x.type)
    if x.verified is not None: fields.append('verified=?');args.append(int(x.verified))
    if fields:
        args.append(user_id);q('UPDATE users SET '+','.join(fields)+' WHERE id=?',args)
    if x.type is not None and x.type in RBAC_ROLES:
        role=q('SELECT id FROM roles WHERE slug=?',(x.type,),True)
        if role:
            q('UPDATE user_roles SET is_primary=0 WHERE user_id=?',(user_id,))
            try: q('INSERT INTO user_roles(user_id,role_id,is_primary,created_at) VALUES(?,?,1,?)',(user_id,role['id'],now()))
            except Exception: q('UPDATE user_roles SET is_primary=1 WHERE user_id=? AND role_id=?',(user_id,role['id']))
    audit(u,'rbac.user.update','user',user_id,metadata={'type':x.type,'verified':x.verified})
    return public_user(q('SELECT * FROM users WHERE id=?',(user_id,),True))

@app.get('/api/v1/department/dashboard')
def department_dashboard(u=Depends(require_permission('admin.dashboard'))):
    r=primary_staff_role(u)
    stats={'department':r}
    if r in ('super_admin','admin'):
        stats.update(users=q('SELECT COUNT(*) n FROM users',(),True)['n'],posts=q('SELECT COUNT(*) n FROM posts',(),True)['n'],products=q('SELECT COUNT(*) n FROM products WHERE active=1',(),True)['n'],open_reports=q("SELECT COUNT(*) n FROM reports WHERE status='open'",(),True)['n'])
    elif r=='market_admin': stats.update(products=q('SELECT COUNT(*) n FROM products',(),True)['n'],orders=q('SELECT COUNT(*) n FROM orders',(),True)['n'])
    elif r=='finance_admin': stats.update(orders=q('SELECT COUNT(*) n FROM orders',(),True)['n'])
    elif r in ('support_admin','moderation_admin'): stats.update(open_reports=q("SELECT COUNT(*) n FROM reports WHERE status='open'",(),True)['n'])
    else: stats.update(records='department scoped')
    return {'user':public_user(u),'roles':role_slugs(u),'permissions':permission_codes(u),'stats':stats}

@app.delete('/api/v1/admin/users/{user_id}')
def admin_delete_user(user_id:str,u=Depends(require_admin)):
    if user_id==u['id']: raise HTTPException(400,'নিজের অ্যাকাউন্ট এখানে মুছতে পারবেন না')
    if not q('SELECT id FROM users WHERE id=?',(user_id,),True): raise HTTPException(404,'User not found')
    q('DELETE FROM users WHERE id=?',(user_id,)); return {'ok':True}

@app.get('/api/v1/admin/reports')
def admin_reports(status:Optional[str]=None,limit:int=100,u=Depends(require_admin)):
    sql='SELECT * FROM reports';args=[]
    if status: sql+=' WHERE status=?';args.append(status)
    sql+=' ORDER BY created_at DESC LIMIT ?';args.append(limit)
    return q(sql,args)

@app.patch('/api/v1/admin/reports/{report_id}')
def admin_report_status(report_id:str,status:str=Query(...),u=Depends(require_admin)):
    if status not in ('open','reviewing','resolved','dismissed'): raise HTTPException(422,'Invalid status')
    if not q('SELECT id FROM reports WHERE id=?',(report_id,),True): raise HTTPException(404,'Report not found')
    q('UPDATE reports SET status=? WHERE id=?',(status,report_id)); return q('SELECT * FROM reports WHERE id=?',(report_id,),True)


# --- Department workspaces (role-scoped operational APIs) ---
class StaffNoteIn(BaseModel):
    text:str=Field(min_length=1,max_length=1000)
class CropStatusIn(BaseModel):
    status:str=Field(min_length=3,max_length=30)
class ProductModerationIn(BaseModel):
    active:bool

@app.get('/api/v1/department/users')
def department_users(limit:int=100, search:Optional[str]=None, u=Depends(me)):
    if primary_staff_role(u) not in ('super_admin','admin','support_admin'):
        raise HTTPException(403,'User workspace access required')
    limit=max(1,min(limit,300)); args=[]
    sql='SELECT id,name,email,phone,type,verified,location,created_at FROM users'
    if search:
        sql+=' WHERE name LIKE ? OR email LIKE ? OR phone LIKE ? OR type LIKE ?'
        pat='%'+search+'%'; args += [pat,pat,pat,pat]
    sql+=' ORDER BY created_at DESC LIMIT ?'; args.append(limit)
    return q(sql,args)

@app.get('/api/v1/department/market/products')
def department_market_products(limit:int=100, active:Optional[bool]=None, u=Depends(require_department('market_admin'))):
    sql='SELECT p.*,u.name seller_name,u.phone seller_phone FROM products p JOIN users u ON u.id=p.seller_id'; args=[]
    if active is not None: sql+=' WHERE p.active=?'; args.append(int(active))
    sql+=' ORDER BY p.created_at DESC LIMIT ?'; args.append(max(1,min(limit,300)))
    return q(sql,args)

@app.patch('/api/v1/department/market/products/{product_id}')
def department_market_product(product_id:str,x:ProductModerationIn,u=Depends(require_department('market_admin'))):
    enforce_work_owner('market_admin','product',product_id,u)
    row=q('SELECT * FROM products WHERE id=?',(product_id,),True)
    if not row: raise HTTPException(404,'Product not found')
    q('UPDATE products SET active=? WHERE id=?',(int(x.active),product_id)); audit(u,'market.product.active','product',product_id,metadata={'active':x.active})
    return q('SELECT * FROM products WHERE id=?',(product_id,),True)

@app.get('/api/v1/department/market/orders')
def department_market_orders(limit:int=100,status:Optional[str]=None,u=Depends(require_department('market_admin'))):
    sql='SELECT o.*,u.name buyer_name,u.phone buyer_phone FROM orders o JOIN users u ON u.id=o.buyer_id'; args=[]
    if status: sql+=' WHERE o.status=?'; args.append(status)
    sql+=' ORDER BY o.created_at DESC LIMIT ?'; args.append(max(1,min(limit,300)))
    rows=q(sql,args)
    for o in rows: o['items']=q('SELECT oi.*,p.name FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?',(o['id'],))
    return rows

@app.patch('/api/v1/department/market/orders/{order_id}')
def department_market_order(order_id:str,status:str=Query(...),u=Depends(require_department('market_admin'))):
    enforce_work_owner('market_admin','order',order_id,u)
    allowed={'pending','confirmed','processing','shipped','delivered','cancelled'}
    if status not in allowed: raise HTTPException(422,'Invalid order status')
    if not q('SELECT id FROM orders WHERE id=?',(order_id,),True): raise HTTPException(404,'Order not found')
    q('UPDATE orders SET status=?,updated_at=? WHERE id=?',(status,now(),order_id)); audit(u,'market.order.status','order',order_id,metadata={'status':status})
    return q('SELECT * FROM orders WHERE id=?',(order_id,),True)


@app.get('/api/v1/department/finance/summary')
def department_finance_summary(u=Depends(require_department('finance_admin'))):
    return {'gross_order_value':q("SELECT COALESCE(SUM(total),0) v FROM orders",(),True)['v'],'orders':q("SELECT COUNT(*) n FROM orders",(),True)['n'],'unpaid_orders':q("SELECT COUNT(*) n FROM orders WHERE payment_status!='paid'",(),True)['n']}

@app.get('/api/v1/department/content/knowledge')
def department_content_knowledge(limit:int=100,u=Depends(require_department('content_admin'))):
    return {'sources':q('SELECT id,title,original_name,kind,size_bytes,status,error,created_by,created_at,updated_at FROM ai_ingestion_sources ORDER BY created_at DESC LIMIT ?',(max(1,min(limit,300)),)),
            'documents':q('SELECT id,title,source,created_at FROM knowledge_documents ORDER BY created_at DESC LIMIT ?',(max(1,min(limit,300)),))}

@app.get('/api/v1/department/content/diagnosis')
def department_content_diagnosis(limit:int=100,u=Depends(require_department('content_admin'))):
    return q('SELECT * FROM ai_diagnosis_cases ORDER BY updated_at DESC LIMIT ?',(max(1,min(limit,300)),))

@app.patch('/api/v1/department/content/diagnosis/{case_id}')
def department_content_diagnosis_update(case_id:str,x:DiagnosisCaseIn,u=Depends(require_department('content_admin'))):
    enforce_work_owner('content_admin','diagnosis_case',case_id,u)
    row=q('SELECT * FROM ai_diagnosis_cases WHERE id=?',(case_id,),True)
    if not row: raise HTTPException(404,'Diagnosis case not found')
    vals=(x.title,x.crop,x.disease,x.pest,x.problem_type,x.symptoms,x.visual_signs,x.causes,x.actions,x.prevention,x.red_flags,x.source,x.confidence,now(),case_id)
    q('UPDATE ai_diagnosis_cases SET title=?,crop=?,disease=?,pest=?,problem_type=?,symptoms=?,visual_signs=?,causes=?,actions=?,prevention=?,red_flags=?,source=?,confidence=?,updated_at=? WHERE id=?',vals)
    audit(u,'ai.diagnosis.case_update','diagnosis_case',case_id); return q('SELECT * FROM ai_diagnosis_cases WHERE id=?',(case_id,),True)

@app.delete('/api/v1/department/content/diagnosis/{case_id}')
def department_content_diagnosis_delete(case_id:str,u=Depends(require_department('content_admin'))):
    enforce_work_owner('content_admin','diagnosis_case',case_id,u)
    if not q('SELECT id FROM ai_diagnosis_cases WHERE id=?',(case_id,),True): raise HTTPException(404,'Diagnosis case not found')
    q('DELETE FROM ai_diagnosis_cases WHERE id=?',(case_id,)); audit(u,'ai.diagnosis.case_delete','diagnosis_case',case_id); return {'ok':True}

@app.get('/api/v1/department/support/reports')
def department_support_reports(status:Optional[str]=None,limit:int=100,u=Depends(require_department('support_admin'))):
    sql='SELECT r.*,u.name reporter_name,u.email,u.phone FROM reports r JOIN users u ON u.id=r.reporter_id'; args=[]
    if status: sql+=' WHERE r.status=?'; args.append(status)
    sql+=' ORDER BY r.created_at DESC LIMIT ?'; args.append(max(1,min(limit,300)))
    return q(sql,args)

@app.patch('/api/v1/department/support/reports/{report_id}')
def department_support_report(report_id:str,status:str=Query(...),u=Depends(require_department('support_admin'))):
    enforce_work_owner('support_admin','report',report_id,u)
    if status not in ('open','reviewing','resolved','dismissed'): raise HTTPException(422,'Invalid status')
    if not q('SELECT id FROM reports WHERE id=?',(report_id,),True): raise HTTPException(404,'Report not found')
    q('UPDATE reports SET status=? WHERE id=?',(status,report_id)); audit(u,'support.report.status','report',report_id,metadata={'status':status}); return q('SELECT * FROM reports WHERE id=?',(report_id,),True)

@app.post('/api/v1/department/support/users/{user_id}/notify')
def department_support_notify(user_id:str,x:StaffNoteIn,u=Depends(require_department('support_admin'))):
    if not q('SELECT id FROM users WHERE id=?',(user_id,),True): raise HTTPException(404,'User not found')
    nid=uid('nt'); q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(nid,user_id,x.text,'support',0,now())); audit(u,'support.user.notify','user',user_id,metadata={'notification_id':nid}); return q('SELECT * FROM notifications WHERE id=?',(nid,),True)

@app.get('/api/v1/department/moderation/posts')
def department_moderation_posts(limit:int=100,u=Depends(require_department('moderation_admin'))):
    return q('SELECT p.*,u.name author_name,u.email FROM posts p JOIN users u ON u.id=p.user_id ORDER BY p.created_at DESC LIMIT ?',(max(1,min(limit,300)),))

@app.delete('/api/v1/department/moderation/posts/{post_id}')
def department_moderation_delete_post(post_id:str,u=Depends(require_department('moderation_admin'))):
    enforce_work_owner('moderation_admin','post',post_id,u)
    row=q('SELECT * FROM posts WHERE id=?',(post_id,),True)
    if not row: raise HTTPException(404,'Post not found')
    q('DELETE FROM posts WHERE id=?',(post_id,)); audit(u,'moderation.post.delete','post',post_id); return {'ok':True}

@app.get('/api/v1/department/moderation/products')
def department_moderation_products(limit:int=100,u=Depends(require_department('moderation_admin'))):
    return q('SELECT p.*,u.name seller_name FROM products p JOIN users u ON u.id=p.seller_id ORDER BY p.created_at DESC LIMIT ?',(max(1,min(limit,300)),))

@app.patch('/api/v1/department/moderation/products/{product_id}')
def department_moderation_product(product_id:str,x:ProductModerationIn,u=Depends(require_department('moderation_admin'))):
    enforce_work_owner('moderation_admin','product',product_id,u)
    row=q('SELECT id FROM products WHERE id=?',(product_id,),True)
    if not row: raise HTTPException(404,'Product not found')
    q('UPDATE products SET active=? WHERE id=?',(int(x.active),product_id)); audit(u,'moderation.product.active','product',product_id,metadata={'active':x.active}); return q('SELECT * FROM products WHERE id=?',(product_id,),True)

# Crop Intelligence: edit/approval lifecycle for department staff.
CROP_TABLES={'categories':'crop_categories','crops':'crops','varieties':'crop_varieties','regions':'crop_regions','stages':'crop_lifecycle_stages','management-rules':'crop_management_rules','pests':'crop_pests','diseases':'crop_diseases','actions':'crop_problem_actions','treatments':'crop_treatments','media':'crop_media','notification-rules':'crop_notification_rules'}
@app.patch('/api/v1/admin/crop-intelligence/{table}/{row_id}/status')
def crop_row_status(table:str,row_id:str,x:CropStatusIn,u=Depends(require_department('crop_admin'))):
    enforce_work_owner('crop_admin',table,row_id,u)
    if table not in CROP_TABLES: raise HTTPException(404,'Unknown crop intelligence table')
    if 'crop.approve' not in permission_codes(u) and 'crop.edit' not in permission_codes(u): raise HTTPException(403,'Crop edit/approval permission required')
    if x.status not in ('draft','review','approved','rejected'): raise HTTPException(422,'Invalid status')
    t=CROP_TABLES[table]; row=q('SELECT * FROM '+t+' WHERE id=?',(row_id,),True)
    if not row: raise HTTPException(404,'Crop record not found')
    q('UPDATE '+t+' SET status=?,updated_at=? WHERE id=?',(x.status,now(),row_id))
    audit(u,'crop_intelligence.status',t,row_id,metadata={'status':x.status}); return q('SELECT * FROM '+t+' WHERE id=?',(row_id,),True)

@app.delete('/api/v1/admin/crop-intelligence/{table}/{row_id}')
def crop_row_delete(table:str,row_id:str,u=Depends(require_department('crop_admin'))):
    enforce_work_owner('crop_admin',table,row_id,u)
    if table not in CROP_TABLES: raise HTTPException(404,'Unknown crop intelligence table')
    t=CROP_TABLES[table]
    if not q('SELECT id FROM '+t+' WHERE id=?',(row_id,),True): raise HTTPException(404,'Crop record not found')
    q('DELETE FROM '+t+' WHERE id=?',(row_id,)); audit(u,'crop_intelligence.delete',t,row_id); return {'ok':True}

# --- Seller-owned payment accounts (System A: direct merchant payment) ---
SUPPORTED_SELLER_PAYMENT_PROVIDERS={'bkash','nagad','rocket','bank'}










# --- Seller Page / Subscription / Market Area / Ads ---
def seller_page_for(u):
    return q('SELECT * FROM seller_pages WHERE user_id=?',(u['id'],),True)

def seller_slug(name):
    base=''.join(ch.lower() if ch.isalnum() else '-' for ch in name).strip('-') or 'seller'
    slug=base
    i=2
    while q('SELECT id FROM seller_pages WHERE slug=?',(slug,),True):
        slug=f'{base}-{i}'; i+=1
    return slug

@app.get('/api/v1/seller/page')
def get_seller_page(u=Depends(me)):
    page=seller_page_for(u)
    if not page: return None
    page['areas']=q('SELECT * FROM seller_market_areas WHERE page_id=? AND active=1 ORDER BY created_at DESC',(page['id'],))
    page['subscriptions']=q('SELECT s.*,p.name_bn,p.price,p.duration_days,p.ad_limit FROM seller_subscriptions s JOIN seller_subscription_plans p ON p.id=s.plan_id WHERE s.page_id=? ORDER BY s.created_at DESC',(page['id'],))
    return page

@app.post('/api/v1/seller/page')
def create_seller_page(x:SellerPageIn,u=Depends(me)):
    if seller_page_for(u): raise HTTPException(409,'Seller page already exists')
    pid=uid('sp'); slug=seller_slug(x.page_name); t=now()
    q('INSERT INTO seller_pages VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,u['id'],x.page_name,slug,x.description or '',_safe_profile_url(x.logo),_safe_profile_url(x.cover),x.phone or u.get('phone'),x.location or u.get('location'),1,t,t))
    return get_seller_page(u)

@app.patch('/api/v1/seller/page')
def update_seller_page(x:SellerPageIn,u=Depends(me)):
    p=seller_page_for(u)
    if not p: raise HTTPException(404,'Seller page not found')
    q('UPDATE seller_pages SET page_name=?,description=?,logo=?,cover=?,phone=?,location=?,updated_at=? WHERE id=?',(x.page_name,x.description or '',_safe_profile_url(x.logo),_safe_profile_url(x.cover),x.phone,x.location,now(),p['id']))
    return get_seller_page(u)

@app.get('/api/v1/seller/subscription-plans')
def seller_subscription_plans(u=Depends(me)):
    return q('SELECT * FROM seller_subscription_plans WHERE active=1 ORDER BY duration_days,price')

@app.post('/api/v1/seller/subscriptions')
def buy_seller_subscription(x:SellerSubscribeIn,u=Depends(me)):
    page=seller_page_for(u)
    if not page: raise HTTPException(400,'প্রথমে Seller Page খুলুন')
    plan=q('SELECT * FROM seller_subscription_plans WHERE id=? AND active=1',(x.plan_id,),True)
    if not plan: raise HTTPException(404,'Subscription plan not found')
    sid=uid('ss'); t=now()
    free_mode=True
    if free_mode:
        starts=datetime.now(timezone.utc); expires=starts+timedelta(days=int(plan['duration_days']))
        q('INSERT INTO seller_subscriptions VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,page['id'],plan['id'],'active','free_launch',None,starts.isoformat(),expires.isoformat(),t,t))
        audit(u,'seller.subscription.activate_free','seller_subscription',sid,metadata={'plan_id':plan['id']})
        return {'id':sid,'status':'active','message':'প্রাথমিক পর্যায়ে এই subscription বিনামূল্যে সক্রিয় হয়েছে','plan':plan,'starts_at':starts.isoformat(),'expires_at':expires.isoformat()}

@app.get('/api/v1/seller/subscriptions')
def seller_subscriptions(u=Depends(me)):
    page=seller_page_for(u)
    if not page:return []
    return q('SELECT s.*,p.name_bn,p.price,p.duration_days,p.ad_limit FROM seller_subscriptions s JOIN seller_subscription_plans p ON p.id=s.plan_id WHERE s.page_id=? ORDER BY s.created_at DESC',(page['id'],))

@app.post('/api/v1/seller/page/areas')
def add_seller_area(x:SellerAreaIn,u=Depends(me)):
    page=seller_page_for(u)
    if not page: raise HTTPException(400,'Seller page required')
    aid=uid('sa'); t=now(); q('INSERT INTO seller_market_areas VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,page['id'],x.division,x.district,x.upazila,x.union_name,x.area_name,x.radius_km,1,t,t)); return q('SELECT * FROM seller_market_areas WHERE id=?',(aid,),True)

@app.delete('/api/v1/seller/page/areas/{area_id}')
def delete_seller_area(area_id:str,u=Depends(me)):
    page=seller_page_for(u)
    if not page: raise HTTPException(404,'Seller page not found')
    if not q('SELECT id FROM seller_market_areas WHERE id=? AND page_id=?',(area_id,page['id']),True): raise HTTPException(404,'Area not found')
    q('DELETE FROM seller_market_areas WHERE id=?',(area_id,)); return {'ok':True}

@app.get('/api/v1/seller/ads')
def seller_ads(u=Depends(me)):
    page=seller_page_for(u)
    if not page:return []
    return q('SELECT a.*,p.name product_name FROM seller_ads a LEFT JOIN products p ON p.id=a.product_id WHERE a.page_id=? ORDER BY a.created_at DESC',(page['id'],))

@app.post('/api/v1/seller/ads')
def create_seller_ad(x:SellerAdIn,u=Depends(me)):
    page=seller_page_for(u)
    if not page: raise HTTPException(400,'প্রথমে Seller Page খুলুন')
    sub=q("SELECT s.*,p.ad_limit FROM seller_subscriptions s JOIN seller_subscription_plans p ON p.id=s.plan_id WHERE s.page_id=? AND s.status='active' AND (s.expires_at IS NULL OR s.expires_at>?) ORDER BY s.expires_at DESC LIMIT 1",(page['id'],now()),True)
    if not sub: raise HTTPException(402,'Active seller subscription required')
    count=q('SELECT COUNT(*) n FROM seller_ads WHERE page_id=? AND created_at>=COALESCE(?,created_at)',(page['id'],sub.get('starts_at')),True)['n']
    if count>=int(sub['ad_limit'] or 0): raise HTTPException(403,'এই subscription-এর ad limit শেষ')
    if x.product_id and not q('SELECT id FROM products WHERE id=? AND seller_id=?',(x.product_id,u['id']),True): raise HTTPException(403,'Product not owned by seller')
    if x.area_id and not q('SELECT id FROM seller_market_areas WHERE id=? AND page_id=?',(x.area_id,page['id']),True): raise HTTPException(403,'Area not owned by seller page')
    aid=uid('ad'); t=now(); q('INSERT INTO seller_ads VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,page['id'],x.product_id,x.headline,x.description or '',_safe_profile_url(x.image),_safe_web_url(x.landing_url),x.area_id,'draft',x.starts_at,x.ends_at,t,t)); audit(u,'seller.ad.create','seller_ad',aid); return q('SELECT * FROM seller_ads WHERE id=?',(aid,),True)

@app.patch('/api/v1/seller/ads/{ad_id}')
def update_seller_ad(ad_id:str,x:SellerAdIn,u=Depends(me)):
    page=seller_page_for(u); ad=q('SELECT * FROM seller_ads WHERE id=? AND page_id=?',(ad_id,page['id'] if page else ''),True)
    if not ad: raise HTTPException(404,'Ad not found')
    if x.product_id and not q('SELECT id FROM products WHERE id=? AND seller_id=?',(x.product_id,u['id']),True): raise HTTPException(403,'Product not owned')
    q('UPDATE seller_ads SET product_id=?,headline=?,description=?,image=?,landing_url=?,area_id=?,starts_at=?,ends_at=?,updated_at=? WHERE id=?',(x.product_id,x.headline,x.description or '',_safe_profile_url(x.image),_safe_web_url(x.landing_url),x.area_id,x.starts_at,x.ends_at,now(),ad_id)); return q('SELECT * FROM seller_ads WHERE id=?',(ad_id,),True)

@app.delete('/api/v1/seller/ads/{ad_id}')
def delete_seller_ad(ad_id:str,u=Depends(me)):
    page=seller_page_for(u); ad=q('SELECT id FROM seller_ads WHERE id=? AND page_id=?',(ad_id,page['id'] if page else ''),True)
    if not ad: raise HTTPException(404,'Ad not found')
    q('DELETE FROM seller_ads WHERE id=?',(ad_id,)); return {'ok':True}

@app.get('/api/v1/marketplace/seller-pages')
def public_seller_pages(limit:int=30,offset:int=0,u=Depends(me)):
    rows=q('SELECT * FROM seller_pages WHERE active=1 ORDER BY created_at DESC LIMIT ? OFFSET ?',(limit,offset))
    for p in rows: p['areas']=q('SELECT * FROM seller_market_areas WHERE page_id=? AND active=1',(p['id'],))
    return rows

@app.get('/api/v1/marketplace/seller-pages/{slug}')
def public_seller_page(slug:str,u=Depends(me)):
    p=q('SELECT * FROM seller_pages WHERE slug=? AND active=1',(slug,),True)
    if not p: raise HTTPException(404,'Seller page not found')
    p['areas']=q('SELECT * FROM seller_market_areas WHERE page_id=? AND active=1',(p['id'],))
    p['products']=q('SELECT id,name,price,unit,category,stock,location,description,tags,images,rating,rating_count FROM products WHERE seller_id=? AND active=1 ORDER BY created_at DESC',(p['user_id'],))
    for x in p['products']:
        x['images']=json.loads(x.get('images') or '[]')
        try:x['tags']=json.loads(x.get('tags') or '[]')
        except Exception:x['tags']=[]
    return p

def _norm_area(v):
    return ' '.join(str(v or '').strip().lower().replace('—','-').split())

def _area_match_user(user:dict, area:dict)->bool:
    # Structured hierarchy is authoritative; free-text is a backward-compatible fallback.
    for key in ('division','district','upazila','union_name','area_name'):
        av=_norm_area(area.get(key)); uv=_norm_area(user.get(key))
        if av and uv and av != uv:
            return False
    structured=any(_norm_area(user.get(k)) for k in ('division','district','upazila','union_name','area_name'))
    if structured: return True
    text=_norm_area(user.get('location'))
    vals=[_norm_area(area.get(k)) for k in ('division','district','upazila','union_name','area_name') if _norm_area(area.get(k))]
    return bool(vals) and any(v in text for v in vals)

@app.get('/api/v1/marketplace/ads')
def marketplace_ads(search:Optional[str]=None,limit:int=20,u=Depends(me)):
    # Target ads only to users whose saved location falls inside the seller-selected area.
    if u.get('type') in ('admin','super_admin','crop_admin','content_admin','market_admin','finance_admin','support_admin','moderation_admin'):
        return []
    rows=q("SELECT a.*,sp.page_name,sp.slug,p.name product_name,p.price,p.unit,p.category,p.stock,p.location,p.description,p.tags,p.images,p.rating,p.rating_count FROM seller_ads a JOIN seller_pages sp ON sp.id=a.page_id LEFT JOIN products p ON p.id=a.product_id WHERE a.status='active' AND sp.active=1 AND (a.starts_at IS NULL OR a.starts_at<=?) AND (a.ends_at IS NULL OR a.ends_at>=?) ORDER BY a.created_at DESC LIMIT ?",(now(),now(),max(1,min(limit,50))))
    out=[]; loc=u.get('location') or ''
    term=(search or '').strip().lstrip('#').lower()
    for ad in rows:
        area=q('SELECT * FROM seller_market_areas WHERE id=? AND active=1',(ad.get('area_id'),),True) if ad.get('area_id') else None
        if not area or not _area_match_user(u,area): continue
        tags=[]
        try: tags=json.loads(ad.get('tags') or '[]')
        except Exception: pass
        hay=' '.join([ad.get('product_name') or '',ad.get('headline') or '',ad.get('description') or '',ad.get('category') or '',' '.join(tags)]).lower()
        if term and term not in hay: continue
        try: ad['images']=json.loads(ad.get('images') or '[]')
        except Exception: ad['images']=[]
        ad['tags']=tags; ad['area']=area
        out.append(ad)
    return out

@app.get('/api/v1/marketplace/search')
def marketplace_search(qstr:Optional[str]=Query(None,alias='q'),limit:int=30,u=Depends(me)):
    # Search product name/title, description, category and #tags, then add targeted ads for the same query.
    term=(qstr or '').strip().lstrip('#').lower()
    products_list=products(search=term or None,limit=limit,offset=0,u=u)
    ads=marketplace_ads(search=term or None,limit=min(20,limit),u=u)
    return {'query':qstr or '', 'products':products_list, 'ads':ads}

@app.patch('/api/v1/department/market/seller-subscriptions/{subscription_id}')
def department_seller_subscription(subscription_id:str,status:str=Query(...),u=Depends(require_department('market_admin'))):
    enforce_work_owner('market_admin','seller_subscription',subscription_id,u)
    if status not in ('pending','active','expired','rejected'): raise HTTPException(422,'Invalid status')
    srow=q('SELECT s.*,p.duration_days FROM seller_subscriptions s JOIN seller_subscription_plans p ON p.id=s.plan_id WHERE s.id=?',(subscription_id,),True)
    if not srow: raise HTTPException(404,'Subscription not found')
    starts=now() if status=='active' else srow.get('starts_at'); expires=None
    if status=='active': expires=(datetime.now(timezone.utc)+timedelta(days=int(srow['duration_days']))).isoformat()
    q('UPDATE seller_subscriptions SET status=?,starts_at=?,expires_at=?,updated_at=? WHERE id=?',(status,starts,expires,now(),subscription_id)); audit(u,'market.subscription.status','seller_subscription',subscription_id,metadata={'status':status}); return q('SELECT * FROM seller_subscriptions WHERE id=?',(subscription_id,),True)

@app.get('/api/v1/department/market/ads')
def department_market_ads(limit:int=100,status:Optional[str]=None,u=Depends(require_department('market_admin'))):
    sql='SELECT a.*,sp.page_name,p.name product_name FROM seller_ads a JOIN seller_pages sp ON sp.id=a.page_id LEFT JOIN products p ON p.id=a.product_id'
    args=[]
    if status: sql+=' WHERE a.status=?'; args.append(status)
    sql+=' ORDER BY a.created_at DESC LIMIT ?'; args.append(max(1,min(limit,300)))
    return q(sql,args)

@app.patch('/api/v1/department/market/ads/{ad_id}')
def department_market_ad_status(ad_id:str,status:str=Query(...),u=Depends(require_department('market_admin'))):
    enforce_work_owner('market_admin','seller_ad',ad_id,u)
    if status not in ('draft','active','paused','rejected','expired'): raise HTTPException(422,'Invalid ad status')
    ad=q('SELECT * FROM seller_ads WHERE id=?',(ad_id,),True)
    if not ad: raise HTTPException(404,'Ad not found')
    q('UPDATE seller_ads SET status=?,updated_at=? WHERE id=?',(status,now(),ad_id)); audit(u,'market.ad.status','seller_ad',ad_id,metadata={'status':status}); return q('SELECT * FROM seller_ads WHERE id=?',(ad_id,),True)

@app.get('/api/v1/department/market/seller-pages')
def department_seller_pages(limit:int=100,u=Depends(require_department('market_admin'))):
    return q('SELECT sp.*,u.name seller_name,u.phone seller_phone FROM seller_pages sp JOIN users u ON u.id=sp.user_id ORDER BY sp.created_at DESC LIMIT ?',(max(1,min(limit,300)),))

# --- Strict department isolation helpers ---
def enqueue_push(user_id,title,body,data=None):
    return q('INSERT INTO push_outbox VALUES(?,?,?,?,?,?,?,?,?,?,?)',(uid('push'),user_id,title,body,json.dumps(data or {},ensure_ascii=False),'pending',0,None,now(),None))

@app.post('/api/v1/admin/notifications/push')
def admin_enqueue_push(x:PushEnqueueIn,u=Depends(require_admin)):
    if not q('SELECT id FROM users WHERE id=?',(x.user_id,),True): raise HTTPException(404,'User not found')
    enqueue_push(x.user_id,x.title,x.body,x.data); audit(u,'push.enqueue','push_outbox',None,metadata={'user_id':x.user_id}); return {'ok':True}

def run_push_outbox(limit=100):
    rows=q("SELECT * FROM push_outbox WHERE status='pending' ORDER BY created_at LIMIT ?",(max(1,min(limit,500)),)); sent=0; failed=0
    for row in rows:
        devices=q('SELECT * FROM device_tokens WHERE user_id=?',(row['user_id'],))
        if not devices:
            q("UPDATE push_outbox SET status='failed',attempts=attempts+1,last_error=? WHERE id=?",('No device token',row['id'])); failed+=1; continue
        ok=False; err=''
        for d in devices:
            try:
                send_push(d['token'],row['title'],row['body'],json.loads(row['data'] or '{}'),d.get('platform')); ok=True
            except Exception as e: err=str(e)[:500]
        if ok:
            q("UPDATE push_outbox SET status='sent',attempts=attempts+1,sent_at=? WHERE id=?",(now(),row['id'])); sent+=1
        else:
            q("UPDATE push_outbox SET status='failed',attempts=attempts+1,last_error=? WHERE id=?",(err,row['id'])); failed+=1
    return {'sent':sent,'failed':failed}

def run_crop_notification_job():
    # Generate notifications using the existing approved crop-rule engine, then enqueue push delivery.
    rows=q("SELECT DISTINCT user_id FROM farmer_crop_profiles WHERE status='active'")
    created=0
    # Reuse the existing route logic by matching each active profile directly.
    for p in q("SELECT * FROM farmer_crop_profiles WHERE status='active'"):
        crop_id=p.get('crop_id')
        age=None
        if p.get('planting_date'):
            try: age=max(0,(datetime.now(timezone.utc).date()-datetime.fromisoformat(str(p['planting_date'])[:10]).date()).days)
            except Exception: age=None
        if age is None: continue
        rules=q("SELECT * FROM crop_notification_rules WHERE crop_id=? AND enabled=1 AND status=? ORDER BY priority DESC",(crop_id,'approved'))
        for r in rules:
            if r.get('age_start_day') is not None and age < r['age_start_day']: continue
            if r.get('age_end_day') is not None and age > r['age_end_day']: continue
            scheduled=now()[:13]
            if q('SELECT id FROM crop_notification_log WHERE profile_id=? AND rule_id=? AND scheduled_for=?',(p['id'],r['id'],scheduled),True): continue
            msg=(r['message_template_bn'] or '').replace('{crop}',str(crop_id)).replace('{age_day}',str(age))
            q('INSERT INTO crop_notification_log VALUES(?,?,?,?,?,?,?,?)',(uid('cnl'),p['id'],r['id'],scheduled,None,'in_app','pending',msg))
            q('INSERT INTO notifications VALUES(?,?,?,?,?,?)',(uid('not'),p['user_id'],msg,'crop_management',0,now()))
            enqueue_push(p['user_id'],r['title_bn'] or 'ফসল ব্যবস্থাপনা',msg,{'kind':'crop_management','crop_id':crop_id})
            created+=1
    return {'created':created}


def run_production_jobs():
    started=now(); jid=uid('job')
    q('INSERT INTO job_runs VALUES(?,?,?,?,?,?,?)',(jid,'production-worker','running',started,None,None,0))
    total=0
    try:
        a=run_crop_notification_job(); b=run_push_outbox(); total=a['created']+b['sent']
        q('UPDATE job_runs SET status=?,finished_at=?,items=? WHERE id=?',('success',now(),total,jid))
        return {'ok':True,'crop_notifications':a,'push':b}
    except Exception as e:
        q('UPDATE job_runs SET status=?,finished_at=?,error=?,items=? WHERE id=?',('failed',now(),str(e)[:1000],total,jid)); raise

@app.post('/api/v1/internal/jobs/run')
def internal_jobs_run(x_api_key:Optional[str]=Header(None)):
    expected=os.getenv('INTERNAL_JOB_KEY','').strip()
    if not expected or not x_api_key or not secrets.compare_digest(x_api_key,expected): raise HTTPException(401,'Invalid job key')
    return run_production_jobs()

@app.get('/api/v1/admin/operations/jobs')
def operations_jobs(limit:int=50,u=Depends(require_admin)):
    return q('SELECT * FROM job_runs ORDER BY started_at DESC LIMIT ?',(max(1,min(limit,200)),))


# Serve the browser/PWA frontend from the project web bundle after API routes.
# API routes are registered above, so /api/* continues to resolve to FastAPI endpoints.
if os.path.isdir(WEB_DIR):
    app.mount('/', StaticFiles(directory=WEB_DIR, html=True), name='frontend')
