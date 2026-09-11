import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app.main import conn, uid, now, pwd, public_user

name=os.getenv('ADMIN_NAME') or (input('Admin name: ').strip() or 'Krishok Connect Admin')
email=os.getenv('ADMIN_EMAIL') or input('Admin email: ').strip()
password=os.getenv('ADMIN_PASSWORD') or input('Admin password: ')
if not email or len(password)<6:
    raise SystemExit('ADMIN_EMAIL and a password of at least 6 characters are required')
c=conn()
try:
    row=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if row:
        c.execute("UPDATE users SET type='super_admin',verified=1 WHERE id=?",(row['id'],))
        c.commit(); print('Promoted existing user to super_admin:', row['id'])
    else:
        u=(uid('u'),name,email,None,pwd.hash(password),'super_admin',1,None,None,None,None,0,0,0,0,now())
        c.execute('INSERT INTO users(id,name,email,phone,password_hash,type,verified,avatar,cover,location,bio,followers,following,rating,rating_count,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',u)
        c.commit(); print('Created super_admin:',u[0])
finally: c.close()
