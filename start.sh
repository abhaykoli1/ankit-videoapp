#!/bin/bash
echo "🎥 VideoCall App Backend Setup"
echo "================================"

cd "$(dirname "$0")"

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate
source venv/bin/activate

# Install requirements
echo "📥 Installing dependencies..."
pip install -r requirements.txt -q

# Create necessary directories
mkdir -p static/uploads/profiles
mkdir -p static/uploads/hosts/pics
mkdir -p static/uploads/hosts/videos

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting server..."
echo "   API Docs:    http://localhost:8000/docs"
echo "   Admin Panel: http://localhost:8000/admin-panel"
echo "   Admin Login: admin / Admin@123"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
