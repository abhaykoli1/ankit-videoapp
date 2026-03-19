from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core.database import connect_db, close_db
from app.routers import auth, hosts, upid_module, wallet, calls, gifts, chat, admin, levels

# Create upload directories
for dir_path in [
    "static/uploads/profiles",
    "static/uploads/hosts/pics", 
    "static/uploads/hosts/videos",
    "admin"
]:
    os.makedirs(dir_path, exist_ok=True)

app = FastAPI(
    title="🎥 VideoCall App API",
    description="""
## VideoCall App - Complete Backend API

### Features:
- 🔐 **Auth**: Register, Login, Guest Mode
- 🏠 **Discover**: Browse admin-added hosts
- 📹 **Video Calls**: Call hosts with real-time billing
- 💰 **Wallet**: Recharge, transactions, coin packages  
- 🎁 **Gifts**: Purchase and send gifts during calls
- 🤖 **Chat Bot**: Hinglish bot 'Priya' 
- 🎯 **Random Match**: Get matched with random hosts
- ⭐ **Levels**: XP-based level progression
- 👮 **Admin**: Full admin panel
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount admin panel
if os.path.exists("admin"):
    app.mount("/admin-panel", StaticFiles(directory="admin", html=True), name="admin-panel")

@app.on_event("startup")
async def startup():
    await connect_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()

# Include all routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(hosts.router, prefix="/api/v1")
app.include_router(wallet.router, prefix="/api/v1")
app.include_router(calls.router, prefix="/api/v1")
app.include_router(gifts.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(levels.router, prefix="/api/v1")
app.include_router(upid_module.router, prefix="/api/v1")

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>VideoCall App API</title>
        <style>
            body { font-family: Arial; background: #1a1a2e; color: #fff; text-align: center; padding: 50px; }
            h1 { color: #e94560; font-size: 2.5em; }
            .links { margin-top: 30px; }
            a { color: #0f3460; background: #e94560; padding: 12px 24px; margin: 10px; 
                border-radius: 8px; text-decoration: none; display: inline-block; font-weight: bold; }
            a:hover { background: #c73652; }
            .badge { background: #0f3460; padding: 5px 15px; border-radius: 20px; margin: 5px; display: inline-block; }
        </style>
    </head>
    <body>
        <h1>🎥 VideoCall App API</h1>
        <p>Complete Backend with FastAPI + MongoDB</p>
        <div>
            <span class="badge">✅ Auth & Guest Mode</span>
            <span class="badge">✅ Discover Hosts</span>
            <span class="badge">✅ Video Calls + Billing</span>
            <span class="badge">✅ Wallet System</span>
            <span class="badge">✅ Gifts Module</span>
            <span class="badge">✅ Hinglish Bot</span>
            <span class="badge">✅ Random Match</span>
            <span class="badge">✅ XP Levels</span>
            <span class="badge">✅ Admin Panel</span>
        </div>
        <div class="links">
            <a href="/docs">📖 API Docs (Swagger)</a>
            <a href="/redoc">📋 ReDoc</a>
            <a href="/admin-panel">👮 Admin Panel</a>
        </div>
    </body>
    </html>
    """

@app.get("/health")
async def health():
    return {"status": "healthy", "app": "VideoCall API", "version": "1.0.0"}
