# Krishok Connect - দ্রুত শুরু করুন ⚡

## **৩০ সেকেন্ডে শুরু করুন**

### Step 1: পূর্বশর্ত চেক করুন
- Docker ইনস্টল করা আছে?
- Git ইনস্টল করা আছে?

### Step 2: এই কমান্ড চালান
```bash
# প্রজেক্ট ডাউনলোড করুন
git clone https://github.com/engashfak29-netizen/Krishok-Connect-2.git
cd Krishok-Connect-2

# Backend চালু করুন
cd backend
docker-compose up -d

# Frontend চালু করুন (নতুন টার্মিনাল)
cd ../web
python -m http.server 3000
```

### Step 3: ব্রাউজারে খুলুন
```
http://localhost:3000
```

---

## **প্রথমবার লগইন করার আগে অ্যাকাউন্ট তৈরি করুন**

### Super Admin তৈরি করুন
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

তারপর, Admin করতে (একবার শুধু):
```bash
# চেক করুন ডাটাবেস আছে কি
docker exec krishok-connect-2-api-1 ls -la ./app/

# Admin আপডেট করুন
docker exec krishok-connect-2-api-1 sqlite3 ./app/krishok_connect.db \
  "UPDATE users SET type='super_admin' WHERE email='admin@krishok.local';"
```

### সাধারণ ইউজার তৈরি করুন
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "রহিম কৃষক",
    "phone": "01711111111",
    "password": "Farmer12345678",
    "type": "farmer"
  }'
```

### বিজনেস ইউজার তৈরি করুন
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "আহমেদ বিক্রেতা",
    "phone": "01799999999",
    "password": "Business12345678",
    "type": "business"
  }'
```

---

## **এখন টেস্ট করুন**

| ভূমিকা | লগইন | পাসওয়ার্ড | ড্যাশবোর্ড |
|--------|------|----------|-----------|
| 🔴 Super Admin | admin@krishok.local | Admin12345678 | /admin/dashboard.html |
| 🟢 Farmer | 01711111111 | Farmer12345678 | / (হোম) |
| 🔵 Business | 01799999999 | Business12345678 | / (হোম) |

---

## **সমস্যা? সমাধান দেখুন**

### Backend দেখা যাচ্ছে না?
```bash
docker ps
# যদি tidak দেখা যায়:
docker-compose down
docker-compose up -d
```

### ফ্রন্টএন্ড লোড হচ্ছে না?
```bash
# নিশ্চিত করুন Python 3+ আছে
python --version

# নতুন টার্মিনাল খুলুন:
cd web
python -m http.server 3000
```

### ডাটাবেস রিসেট করতে চান?
```bash
# সব কিছু মুছুন এবং শুরু করুন
docker-compose down -v
docker-compose up -d
```

---

## **পরবর্তী ধাপ**

✅ সব ড্যাশবোর্ড টেস্ট করুন  
✅ বাগ খুঁজে বের করুন এবং রিপোর্ট করুন  
✅ কোডে উন্নতি করুন  
✅ তারপর লাইভ ডিপ্লয় করুন  

---

📖 বিস্তারিত গাইডের জন্য `DEVELOPMENT_SETUP.md` পড়ুন।
