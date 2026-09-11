from pathlib import Path
import ast, re, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
BACKEND=Path(__file__).resolve().parent
errors=[]
try: ast.parse((BACKEND/'app'/'main.py').read_text(encoding='utf-8'))
except Exception as e: errors.append(f'Python syntax: {e}')
for f in ROOT.rglob('*.js'):
    r=subprocess.run(['node','--check',str(f)],capture_output=True,text=True)
    if r.returncode: errors.append(f'JS syntax: {f}: {r.stderr.strip()}')
s=(BACKEND/'app'/'main.py').read_text(encoding='utf-8')
methods=re.findall(r"@app\.(get|post|put|patch|delete|websocket)\(['\"]([^'\"]+)",s)
if len(methods)!=len(set(methods)): errors.append('Duplicate HTTP method+path route detected')
required=[
 'farmer/ai-context','farmer/farm/journal','farmer/notifications/generate',
 'conversations/{cid}/read','media/upload','calls/config',
 'orders/{order_id}/delivery'
]
for x in required:
    if not any(x in p for _,p in methods): errors.append(f'Missing route: {x}')
print(f'Project root: {ROOT}')
print(f'Python routes: {len(methods)}')
print(f'JS files checked: {len(list(ROOT.rglob("*.js")))}')
print('RESULT: PASS' if not errors else 'RESULT: FAIL')
for e in errors: print(' -',e)
sys.exit(1 if errors else 0)
