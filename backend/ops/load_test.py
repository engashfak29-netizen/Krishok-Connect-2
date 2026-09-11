#!/usr/bin/env python3
"""Simple async HTTP load test. Usage: python load_test.py URL [concurrency] [requests]."""
import asyncio,sys,time
try: import httpx
except ImportError: raise SystemExit('Install requirements first (httpx).')
base=(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000').rstrip('/'); concurrency=int(sys.argv[2]) if len(sys.argv)>2 else 100; total=int(sys.argv[3]) if len(sys.argv)>3 else 1000
async def main():
    sem=asyncio.Semaphore(concurrency); ok=err=0; lat=[]
    async with httpx.AsyncClient(timeout=20) as c:
        async def one(i):
            nonlocal ok,err
            async with sem:
                t=time.perf_counter()
                try:
                    r=await c.get(base+'/health'); lat.append(time.perf_counter()-t); ok += r.status_code==200; err += r.status_code!=200
                except Exception: err+=1
        await asyncio.gather(*(one(i) for i in range(total)))
    lat.sort(); p95=lat[min(len(lat)-1,max(0,int(len(lat)*.95)-1))] if lat else 0
    print({'requests':total,'concurrency':concurrency,'ok':ok,'errors':err,'p95_seconds':round(p95,3)})
asyncio.run(main())
