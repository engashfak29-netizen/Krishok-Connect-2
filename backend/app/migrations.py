from __future__ import annotations
import os, sqlite3
try:
    import psycopg
except Exception:
    psycopg=None

MIGRATIONS_DIR=os.path.join(os.path.dirname(os.path.dirname(__file__)),'migrations')

def run_migrations(database_url):
    use_pg=database_url.startswith(('postgresql://','postgres://'))
    if use_pg:
        if psycopg is None: raise RuntimeError('psycopg is required for PostgreSQL migrations')
        conn=psycopg.connect(database_url)
    else:
        path=database_url.replace('sqlite:///./','')
        if not os.path.isabs(path): path=os.path.join(os.path.dirname(os.path.dirname(__file__)),path)
        conn=sqlite3.connect(path)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
        files=sorted(x for x in os.listdir(MIGRATIONS_DIR) if x.endswith('.sql'))
        for fn in files:
            version=fn.split('_',1)[0]
            cur=conn.execute(("SELECT 1 FROM schema_migrations WHERE version=%s" if use_pg else "SELECT 1 FROM schema_migrations WHERE version=?"),(version,))
            if cur.fetchone(): continue
            sql=open(os.path.join(MIGRATIONS_DIR,fn),encoding='utf-8').read()
            for statement in [s.strip() for s in sql.split(';') if s.strip()]:
                try: conn.execute(statement)
                except Exception as exc:
                    if 'duplicate column' in str(exc).lower() or 'already exists' in str(exc).lower(): continue
                    raise
            conn.execute(("INSERT INTO schema_migrations(version,applied_at) VALUES(%s,CURRENT_TIMESTAMP)" if use_pg else "INSERT INTO schema_migrations(version,applied_at) VALUES(?,CURRENT_TIMESTAMP)"),(version,))
            conn.commit()
    finally: conn.close()
