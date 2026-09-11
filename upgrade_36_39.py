from pathlib import Path
p=Path('/mnt/data/rbac-work/n36_39/backend/app/main.py')
s=p.read_text()
# add call schema after call_events
needle='"CREATE TABLE IF NOT EXISTS call_events(id TEXT PRIMARY KEY,room_id TEXT NOT NULL,user_id TEXT NOT NULL,event TEXT NOT NULL,created_at TEXT NOT NULL)",'
repl=needle+'''\n      "CREATE TABLE IF NOT EXISTS call_sessions(id TEXT PRIMARY KEY,room_id TEXT NOT NULL,caller_id TEXT NOT NULL,callee_id TEXT,call_type TEXT NOT NULL DEFAULT 'video',status TEXT NOT NULL DEFAULT 'ringing',started_at TEXT NOT NULL,answered_at TEXT,ended_at TEXT,ended_by TEXT,FOREIGN KEY(caller_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(callee_id) REFERENCES users(id) ON DELETE SET NULL)",\n      "CREATE INDEX IF NOT EXISTS idx_call_sessions_room ON call_sessions(room_id,status)",\n      "CREATE INDEX IF NOT EXISTS idx_call_sessions_callee ON call_sessions(callee_id,status)" ,'''
s=s.replace(needle,repl)
# Insert call REST models/endpoints before websocket calls
needle2="@app.websocket('/ws/calls/{room_id}')"
insert=r'''class CallCreate(BaseModel):
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

'''
s=s.replace(needle2,insert+needle2)
# fix websocket auth and membership
old="""@app.websocket('/ws/calls/{room_id}')\nasync def calls(room_id:str, websocket:WebSocket, authorization:Optional[str]=Query(None)):\n    try: user=user_from_token(authorization)\n    except HTTPException: await websocket.close(code=1008); return\n    await websocket.accept(); call_connections.setdefault(room_id,set()).add(websocket)"""
new="""@app.websocket('/ws/calls/{room_id}')\nasync def calls(room_id:str, websocket:WebSocket, authorization:Optional[str]=Query(None), token:Optional[str]=Query(None)):\n    try:\n        auth=authorization or (('Bearer '+token) if token else None)\n        user=user_from_token(auth)\n        call=q('SELECT * FROM call_sessions WHERE room_id=? AND (caller_id=? OR callee_id=?) AND status IN ('ringing','connected') ORDER BY started_at DESC LIMIT 1',(room_id,user['id'],user['id']),True)\n        if not call: await websocket.close(code=4403); return\n    except HTTPException: await websocket.close(code=1008); return\n    await websocket.accept(); call_connections.setdefault(room_id,set()).add(websocket)"""
s=s.replace(old,new)
# enrich diagnosis model endpoint if fields exist: locate class
s=s.replace("class DiagnosisIn(BaseModel):\n    symptom:str", "class DiagnosisIn(BaseModel):\n    symptom:str") if "class DiagnosisIn" in s else s
p.write_text(s)
