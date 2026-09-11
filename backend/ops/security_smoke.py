#!/usr/bin/env python3
"""Non-destructive production security smoke checks."""
import sys,urllib.request,urllib.error
base=(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000').rstrip('/')
checks=[('/health',200),('/ready',200),('/api/v1/media/nonexistent',401)]
for path,want in checks:
    try:
        r=urllib.request.urlopen(base+path,timeout=8); code=r.status
    except urllib.error.HTTPError as e: code=e.code
    except Exception as e: print(path,'ERROR',e); continue
    print(path,code,'PASS' if code==want else 'CHECK')
print('Security smoke test complete; use a dedicated DAST/pentest suite for certification.')
