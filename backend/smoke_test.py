#!/usr/bin/env python3
"""Deployment smoke test. Usage: python smoke_test.py https://example.com"""
import json, sys, urllib.request
base=(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000').rstrip('/')
checks=['/health','/ready']
for path in checks:
    try:
        with urllib.request.urlopen(base+path, timeout=8) as r:
            body=r.read().decode('utf-8','replace')
            print(path, r.status, body[:500])
            if r.status != 200: raise SystemExit(1)
    except Exception as e:
        print(path, 'FAIL', e)
        raise SystemExit(2)
print('SMOKE TEST: PASS')
