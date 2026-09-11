from .main import q, now

def seed_crop_catalog():
    cats=[('field','মাঠ ফসল','Field Crops',1),('vegetable','সবজি ফসল','Vegetable Crops',2),('fruit','ফলজ ও বহুবর্ষজীবী','Fruit & Perennial Crops',3)]
    for slug,bn,en,order in cats:
        if not q('SELECT id FROM crop_categories WHERE slug=?',(slug,),True):
            cid='cat_'+slug; ts=now(); q('INSERT INTO crop_categories VALUES(?,?,?,?,?,?,?,?)',(cid,bn,en,slug,order,1,ts,ts))
    data={
      'field':['ধান','গম','ভুট্টা','পাট','আলু','মসুর ডাল','মুগ ডাল','ছোলা','সরিষা','তিল','চিনাবাদাম','সূর্যমুখী','আখ','তুলা'],
      'vegetable':['টমেটো','বেগুন','মরিচ','ফুলকপি','বাঁধাকপি','লাউ','শসা','করলা','ঝিঙা','চিচিঙ্গা','ঢেঁড়স','বরবটি','মিষ্টি কুমড়া','গাজর','মূলা','পালংশাক','পেঁয়াজ','রসুন','আদা','হলুদ'],
      'fruit':['আম','কাঁঠাল','পেয়ারা','লিচু','কলা','পেঁপে','নারিকেল','সুপারি','লেবু জাতীয় ফল','আনারস','কুল','ড্রাগন ফল','তরমুজ','বাঙ্গি']
    }
    for cat, crops in data.items():
        c=q('SELECT id FROM crop_categories WHERE slug=?',(cat,),True)
        for i,bn in enumerate(crops,1):
            slug=cat+'-'+str(i)
            if not q('SELECT id FROM crops WHERE slug=?',(slug,),True):
                cid='crop_'+slug; ts=now(); perennial=1 if cat=='fruit' else 0
                q('INSERT INTO crops VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,c['id'],bn,None,slug,None,None,perennial,1,ts,ts))
    regions=[('বারিন্দ অঞ্চল','Barind','BARIND'),('হাওর অঞ্চল','Haor','HAOR'),('উপকূলীয় অঞ্চল','Coastal','COASTAL'),('চর অঞ্চল','Char','CHAR'),('পার্বত্য অঞ্চল','Hill','HILL'),('সাধারণ সমতল অঞ্চল','Plain','PLAIN')]
    for bn,en,code in regions:
        if not q('SELECT id FROM crop_regions WHERE code=?',(code,),True):
            rid='reg_'+code.lower(); q('INSERT INTO crop_regions VALUES(?,?,?,?,?,?,?)',(rid,bn,en,code,None,1,now()))
