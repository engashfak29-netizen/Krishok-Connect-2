#!/bin/bash

# Krishok Connect - Local Development Runner Script

echo "🚀 Krishok Connect - লোকাল ডেভেলপমেন্ট সেটআপ শুরু হচ্ছে..."
echo "=================================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker ইনস্টল করা নেই। প্রথমে Docker ডাউনলোড করুন: https://www.docker.com/products/docker-desktop"
    exit 1
fi

echo "✅ Docker পাওয়া গেছে"

# Create necessary directories
echo "📁 ফোল্ডার তৈরি করছি..."
mkdir -p media
mkdir -p ai_knowledge_uploads
mkdir -p app

# Check if .env.dev exists, if not copy from example
if [ ! -f ".env.dev" ]; then
    echo "⚙️ Environment ফাইল তৈরি করছি..."
    cat > .env.dev << 'EOF'
DATABASE_URL=sqlite:///./krishok_connect.db
SECRET_KEY=dev-secret-key-for-local-testing-min-32-chars-long-enough
ACCESS_TOKEN_EXPIRE_MINUTES=10080
ENVIRONMENT=development
CORS_ORIGINS=*
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_MAX_REQUESTS=120
LOGIN_MAX_FAILURES=5
LOGIN_LOCK_MINUTES=15
MEDIA_DIR=./media
MEDIA_MAX_FILE_MB=50
MEDIA_STORAGE_BACKEND=local
AI_MAX_FILE_MB=500
REDIS_URL=
REQUIRE_REDIS=false
LOG_LEVEL=INFO
ENABLE_API_DOCS=true
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
MARKET_PRICE_URL=
TURN_SERVERS_JSON=[]
INTERNAL_JOB_KEY=dev-job-key-local-testing
EOF
fi

# Stop existing containers
echo "🛑 পুরাতন কনটেইনার বন্ধ করছি..."
docker-compose down 2>/dev/null || true

# Start new containers
echo "🐳 ডকার কনটেইনার চালু করছি..."
docker-compose up -d

# Wait for container to start
echo "⏳ Backend শুরু হওয়ার জন্য অপেক্ষা করছি..."
sleep 5

# Check if container is running
if docker-compose ps | grep -q "krishok-connect-api"; then
    echo "✅ Backend API চলছে: http://localhost:8000"
    echo "✅ API Docs: http://localhost:8000/docs"
    echo "✅ Health Check: http://localhost:8000/health"
else
    echo "❌ Backend চালু হতে ব্যর্থ হয়েছে"
    docker-compose logs api
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ সব কিছু প্রস্তুত!"
echo "=================================================="
echo ""
echo "📍 পরবর্তী ধাপ:"
echo "1️⃣ নতুন টার্মিনাল খুলুন এবং এটি চালান:"
echo "   cd ../web && python -m http.server 3000"
echo ""
echo "2️⃣ ব্রাউজারে খুলুন:"
echo "   http://localhost:3000"
echo ""
echo "3️⃣ অ্যাকাউন্ট তৈরি করুন (QUICK_START.md দেখুন)"
echo ""
echo "📖 বিস্তারিত জন্য: DEVELOPMENT_SETUP.md"
echo ""
echo "🐳 Docker লগ দেখতে:"
echo "   docker-compose logs -f api"
echo ""
echo "❌ বন্ধ করতে:"
echo "   docker-compose down"
echo ""
