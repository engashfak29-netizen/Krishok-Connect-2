"""One-time SQLite -> PostgreSQL data migration helper.
Usage: set SOURCE_SQLITE and TARGET_DATABASE_URL, then run this script.
It copies tables/rows using column names and preserves IDs.
"""
import os, sqlite3
import psycopg
from psycopg.rows import dict_row

SOURCE=os.getenv('SOURCE_SQLITE','./krishok_connect.db')
TARGET=os.getenv('TARGET_DATABASE_URL','')
if not TARGET: raise SystemExit('TARGET_DATABASE_URL is required')
s=sqlite3.connect(SOURCE); s.row_factory=sqlite3.Row
p=psycopg.connect(TARGET,row_factory=dict_row)
try:
    tables=[r[0] for r in s.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for table in tables:
        cols=[r[1] for r in s.execute(f'PRAGMA table_info("{table}")')]
        rows=s.execute(f'SELECT * FROM "{table}"').fetchall()
        if not cols: continue
        placeholders=','.join(['%s']*len(cols)); colsql=','.join('"'+c+'"' for c in cols)
        for row in rows:
            vals=[row[c] for c in cols]
            p.execute(f'INSERT INTO "{table}" ({colsql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING',vals)
    p.commit()
    print(f'Migrated {len(tables)} tables successfully.')
finally:
    p.close(); s.close()
