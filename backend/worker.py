"""Production worker with safe single-loop scheduling.
Usage: python worker.py --loop 60
"""
import os, sys, time, argparse, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.main import run_production_jobs
logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'))
parser=argparse.ArgumentParser(); parser.add_argument('--loop',type=int,default=0); args=parser.parse_args()
if args.loop <= 0:
    print(run_production_jobs())
else:
    while True:
        try: print(run_production_jobs(), flush=True)
        except Exception as e: logging.exception('production worker failed: %s',e)
        time.sleep(max(10,args.loop))
