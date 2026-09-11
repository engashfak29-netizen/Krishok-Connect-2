"""Production service adapters for Krishok Connect.
All provider credentials/configuration come from environment variables.
"""
from __future__ import annotations
import os, json, time, urllib.request, hashlib, hmac, base64
from datetime import datetime, timezone

try:
    import boto3
except Exception:
    boto3 = None
try:
    import httpx
except Exception:
    httpx = None
import jwt

def utcnow(): return datetime.now(timezone.utc).isoformat()

def http_json(url, payload, headers=None, timeout=20):
    body=json.dumps(payload, ensure_ascii=False).encode()
    h={'Content-Type':'application/json','Accept':'application/json','User-Agent':'KrishokConnect/production'}
    if headers: h.update(headers)
    req=urllib.request.Request(url,data=body,headers=h,method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read().decode()
        return json.loads(raw) if raw else {}

def _headers(prefix):
    raw=os.getenv(f'{prefix}_HEADERS_JSON','').strip()
    return json.loads(raw) if raw else {}



def _fcm_access_token():
    raw=os.getenv('FCM_SERVICE_ACCOUNT_JSON','').strip()
    if not raw: raise RuntimeError('FCM_SERVICE_ACCOUNT_JSON is not configured')
    sa=json.loads(raw); now_i=int(time.time())
    assertion=jwt.encode({'iss':sa['client_email'],'scope':'https://www.googleapis.com/auth/firebase.messaging','aud':'https://oauth2.googleapis.com/token','iat':now_i,'exp':now_i+3600},sa['private_key'],algorithm='RS256')
    data=urllib.parse.urlencode({'grant_type':'urn:ietf:params:oauth:grant-type:jwt-bearer','assertion':assertion}).encode()
    req=urllib.request.Request('https://oauth2.googleapis.com/token',data=data,headers={'Content-Type':'application/x-www-form-urlencoded'},method='POST')
    with urllib.request.urlopen(req,timeout=15) as r: return json.loads(r.read().decode())['access_token'],sa['project_id']

def _send_fcm(token,title,body,data):
    access,project=_fcm_access_token()
    payload={'message':{'token':token,'notification':{'title':title,'body':body},'data':{str(k):str(v) for k,v in (data or {}).items()}}}
    return http_json(f'https://fcm.googleapis.com/v1/projects/{project}/messages:send',payload,{'Authorization':'Bearer '+access},20)

def _apns_private_key():
    raw=os.getenv('APNS_PRIVATE_KEY','').strip()
    if raw: return raw.replace('\\n','\n')
    path=os.getenv('APNS_PRIVATE_KEY_PATH','').strip()
    if path and os.path.isfile(path): return open(path,'r',encoding='utf-8').read()
    raise RuntimeError('APNS_PRIVATE_KEY or APNS_PRIVATE_KEY_PATH is not configured')

def _send_apns(token,title,body,data):
    if httpx is None: raise RuntimeError('httpx is required for APNs HTTP/2')
    kid=os.getenv('APNS_KEY_ID','').strip(); team=os.getenv('APNS_TEAM_ID','').strip(); bundle=os.getenv('APNS_BUNDLE_ID','').strip()
    if not all((kid,team,bundle)): raise RuntimeError('APNs key/team/bundle configuration is incomplete')
    now_i=int(time.time()); key=_apns_private_key()
    bearer=jwt.encode({'iss':team,'iat':now_i},key,algorithm='ES256',headers={'kid':kid})
    host='api.sandbox.push.apple.com' if os.getenv('APNS_USE_SANDBOX','false').lower()=='true' else 'api.push.apple.com'
    payload={'aps':{'alert':{'title':title,'body':body},'sound':'default'}}
    if data: payload.update(data)
    with httpx.Client(http2=True,timeout=20) as client:
        r=client.post(f'https://{host}/3/device/{token}',headers={'authorization':'bearer '+bearer,'apns-topic':bundle,'apns-push-type':'alert','apns-priority':'10','content-type':'application/json'},json=payload)
        if r.status_code>=300: raise RuntimeError(f'APNs {r.status_code}: {r.text[:300]}')
        return r.json() if r.text else {'status':'sent'}

def send_push(device_token, title, body, data=None, platform=None):
    platform=(platform or '').lower()
    if platform in ('ios','ipad','iphone','apns') and (os.getenv('APNS_KEY_ID') or os.getenv('APNS_PRIVATE_KEY')):
        return {'sent':True,'configured':True,'provider':'apns','result':_send_apns(device_token,title,body,data)}
    if platform in ('android','fcm') and os.getenv('FCM_SERVICE_ACCOUNT_JSON'):
        return {'sent':True,'configured':True,'provider':'fcm','result':_send_fcm(device_token,title,body,data)}
    url=os.getenv('PUSH_API_URL','').strip()
    if not url: raise RuntimeError('No push provider configured for this platform')
    result=http_json(url,{'token':device_token,'platform':platform,'title':title,'body':body,'data':data or {}},_headers('PUSH_API'),20)
    return {'sent':True,'configured':True,'provider':'custom','result':result}

def media_put(object_key, data, content_type):
    backend=os.getenv('MEDIA_STORAGE_BACKEND','local').lower()
    if backend=='local':
        root=os.getenv('MEDIA_DIR','').strip() or os.path.join(os.path.dirname(__file__),'..','media')
        os.makedirs(root,exist_ok=True)
        with open(os.path.join(root,object_key),'wb') as f: f.write(data)
        return {'backend':'local','object_key':object_key}
    if backend not in ('s3','external'): raise RuntimeError('Invalid MEDIA_STORAGE_BACKEND')
    if boto3 is None: raise RuntimeError('boto3 is required for object storage')
    bucket=os.getenv('S3_BUCKET','').strip()
    if not bucket: raise RuntimeError('S3_BUCKET is not configured')
    client=boto3.client('s3',endpoint_url=os.getenv('S3_ENDPOINT_URL') or None,region_name=os.getenv('S3_REGION','us-east-1'),aws_access_key_id=os.getenv('S3_ACCESS_KEY_ID') or None,aws_secret_access_key=os.getenv('S3_SECRET_ACCESS_KEY') or None)
    client.put_object(Bucket=bucket,Key=object_key,Body=data,ContentType=content_type)
    return {'backend':'s3','object_key':object_key}

def sha256_bytes(data:bytes): return hashlib.sha256(data).hexdigest()

def signed_download_url(base_url, object_key, secret, ttl=900):
    expires=int(time.time())+max(60,min(ttl,86400)); canonical=f'{object_key}:{expires}'
    sig=hmac.new(secret.encode(),canonical.encode(),hashlib.sha256).hexdigest()
    return f'{base_url.rstrip("/")}/{object_key}?expires={expires}&sig={sig}'


def media_url(object_key):
    backend=os.getenv('MEDIA_STORAGE_BACKEND','local').lower()
    if backend=='local': return '/media/'+object_key
    if boto3 is None: raise RuntimeError('boto3 is required for object storage')
    bucket=os.getenv('S3_BUCKET','').strip()
    if not bucket: raise RuntimeError('S3_BUCKET is not configured')
    client=boto3.client('s3',endpoint_url=os.getenv('S3_ENDPOINT_URL') or None,region_name=os.getenv('S3_REGION','us-east-1'),aws_access_key_id=os.getenv('S3_ACCESS_KEY_ID') or None,aws_secret_access_key=os.getenv('S3_SECRET_ACCESS_KEY') or None)
    cdn=os.getenv('MEDIA_CDN_BASE_URL','').strip()
    if cdn and os.getenv('MEDIA_CDN_PUBLIC','false').lower()=='true': return cdn.rstrip('/')+'/'+object_key
    return client.generate_presigned_url('get_object',Params={'Bucket':bucket,'Key':object_key},ExpiresIn=max(60,min(int(os.getenv('MEDIA_SIGNED_URL_TTL','900')),86400)))
