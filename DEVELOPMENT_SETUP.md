# Krishok Connect - Local Development Setup Guide

আপনার সম্পূর্ণ Krishok Connect প্রজেক্ট লোকালি চালানোর জন্য এই গাইড অনুসরণ করুন।

---

## **প্রয়োজনীয় সফটওয়্যার ইনস্টল করুন**

### Windows / Mac / Linux

1. **Docker Desktop** - ডাউনলোড করুন: https://www.docker.com/products/docker-desktop
2. **Git** - ডাউনলোড করুন: https://git-scm.com/downloads
3. **Node.js** - ডাউনলোড করুন: https://nodejs.org/ (LTS সংস্করণ)

---

## **পদ্ধতি ১: দ্রুত শুরু (Docker এর সাথে) ⚡**

### Step 1: প্রজেক্ট ক্লোন করুন
```bash
git clone https://github.com/engashfak29-netizen/Krishok-Connect-2.git
cd Krishok-Connect-2
```

### Step 2: Backend চালু করুন (Docker)
```bash
cd backend
docker-compose up -d
```

এটি:
- ✅ FastAPI সার্ভার চালু করবে (http://localhost:8000)
- ✅ SQLite ডাটাবেস তৈরি করবে
- ✅ সব এপিআই endpoint প্রস্তুত করবে

**চেক করুন যে সার্ভার চলছে:**
```
http://localhost:8000/health
```
Response হবে: `{"ok": true, "service": "krishok-connect-api", ...}`

### Step 3: Frontend ওয়েব অ্যাপ খুলুন
```bash
cd ../web
# একটি সাধারণ HTTP সার্ভার খুলুন
python -m http.server 3000
```

এখন খুলুন: **http://localhost:3000**

---

## **পদ্ধতি ২: ম্যানুয়াল সেটআপ (ডেভেলপারদের জন্য)**

### Backend (Python):
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Web):
```bash
cd web
python -m http.server 3000
```

---

## **ডেমো অ্যাকাউন্ট তৈরি করুন**

### Super Admin অ্যাকাউন্ট
API থেকে সরাসরি তৈরি করুন (curl বা Postman):

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "সুপার এডমিন",
    "email": "admin@krishok.local",
    "password": "Admin12345678",
    "type": "farmer"
  }'
```

এর পরে, ডাটাবেস থেকে এই ইউজারকে Admin করতে:
```bash
# Backend কনটেইনার এ প্রবেশ করুন
docker exec -it krishok-connect-2-api-1 sqlite3 ./app/krishok_connect.db

# এই কমান্ড চালান:
UPDATE users SET type='super_admin' WHERE email='admin@krishok.local';
```

### সাধারণ ইউজার অ্যাকাউন্ট (Farmer)
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "কৃষক রহিম",
    "phone": "01711111111",
    "password": "Farmer12345678",
    "type": "farmer"
  }'
```

### বিজনেস/বিক্রেতা অ্যাকাউন্ট
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "দোকানদার আহমেদ",
    "phone": "01799999999",
    "password": "Business12345678",
    "type": "business"
  }'
```

---

## **প্রতিটি প্যানেল টেস্ট করুন**

### 1️⃣ **Super Admin Dashboard**
- URL: `http://localhost:3000/admin/dashboard.html`
- লগইন:
  - Email: `admin@krishok.local`
  - পাসওয়ার্ড: `Admin12345678`

**যা টেস্ট করতে পারবেন:**
- ✅ সব ইউজার দেখুন
- ✅ পণ্য ম্যানেজমেন্ট
- ✅ অর্ডার ট্র্যাকিং
- ✅ ফসল বিষয়ক বুদ্ধিমত্তা যোগ করুন
- ✅ রিপোর্ট দেখুন

### 2️⃣ **Farmer Dashboard**
- URL: `http://localhost:3000/`
- লগইন:
  - ফোন: `01711111111`
  - পাসওয়ার্ড: `Farmer12345678`

**যা টেস্ট করতে পারবেন:**
- ✅ খামার তৈরি করুন
- ✅ ফসল যোগ করুন
- ✅ সার/পানির লেখা রাখুন
- ✅ এআই অ্যাডভাইস পান
- ✅ পোস্ট/কমেন্ট করুন
- ✅ আবহাওয়া দেখুন

### 3️⃣ **Business/Seller Dashboard**
- URL: `http://localhost:3000/`
- লগইন:
  - ফোন: `01799999999`
  - পাসওয়ার্ড: `Business12345678`

**যা টেস্ট করতে পারবেন:**
- ✅ পণ্য তৈরি করুন
- ✅ বিক্রয়ের দাম সেট করুন
- ✅ বিক্রয়ের জন্য ইনভেন্টরি পরিচালনা করুন
- ✅ সেলার পেজ তৈরি করুন
- ✅ অর্ডার গ্রহণ করুন

### 4️⃣ **মোবাইল অ্যাপ (PWA)**
- URL: `http://localhost:3000/mobile/` (যদি থাকে)
- অথবা একই ওয়েব অ্যাপ মোবাইল ব্রাউজারে খুলুন

**মোবাইল ফিচার টেস্ট:**
- ✅ রেসপন্সিভ ডিজাইন
- ✅ অফলাইন ক্ষমতা
- ✅ পুশ নোটিফিকেশন (যদি সেটআপ হয়)

---

## **সমস্যা সমাধান**

### ❌ "Backend সংযোগ ব্যর্থ"
```bash
# চেক করুন Docker চলছে কি না
docker ps

# Backend লগ দেখুন
docker logs krishok-connect-2-api-1

# Backend পুনরায় চালু করুন
docker-compose restart
```

### ❌ "Frontend লোড হচ্ছে না"
```bash
# পোর্ট 3000 ব্যবহৃত আছে কি না চেক করুন
netstat -an | grep 3000

# অন্য পোর্টে চালু করুন
python -m http.server 4000
```

### ❌ "CORS Error"
এটি স্বাভাবিক। প্রোডাকশনে, সঠিক CORS সেটিংস সেট করুন।

---

## **ডাটাবেস রিসেট করুন (যদি প্রয়োজন)**

```bash
# Backend কনটেইনারে প্রবেশ করুন
docker exec -it krishok-connect-2-api-1 bash

# ডাটাবেস ফাইল মুছুন
rm ./app/krishok_connect.db

# কনটেইনার বন্ধ করুন
docker-compose down

# পুনরায় চালু করুন
docker-compose up -d
```

নতুন ডাটাবেস স্বয়ংক্রিয়ভাবে তৈরি হবে।

---

## **পোর্ট ম্যাপিং**

| সেবা | URL | পোর্ট |
|------|-----|-------|
| Backend API | http://localhost:8000 | 8000 |
| Frontend Web | http://localhost:3000 | 3000 |
| API Docs (Swagger) | http://localhost:8000/docs | 8000 |
| Database (SQLite) | ./backend/app/krishok_connect.db | - |

---

## **পরবর্তী ধাপ**

✅ স্থানীয়ভাবে সব কিছু টেস্ট করুন
✅ বাগ রিপোর্ট করুন
✅ ফিচার উন্নত করুন
✅ তারপর ডমেইন কিনুন এবং লাইভ ডিপ্লয় করুন

---

**কোনো প্রশ্ন থাকলে জানান!** 🎯
