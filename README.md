# 🎥 VideoCall App - Complete Backend

FastAPI + MongoDB backend for a video calling app with admin panel.

## 🚀 Quick Start

```bash
# 1. MongoDB chalao (localhost:27017)
# 2. Run karo:
bash start.sh

# Ya manually:
pip install -r requirements.txt
uvicorn main:app --reload
```

- **API Docs:** http://localhost:8000/docs
- **Admin Panel:** http://localhost:8000/admin-panel
- **Admin Login:** `admin` / `Admin@123`

---

## 📋 All API Endpoints

### 🔐 AUTH — `/api/v1/auth`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | New user register (form-data: name, mobile, password, gender, profile_picture) |
| POST | `/auth/login` | Login (form-data: mobile, password) |
| POST | `/auth/guest-login` | Guest mode login |
| GET | `/auth/me` | Current user profile (Bearer token) |
| PUT | `/auth/profile` | Update profile |
| POST | `/auth/convert-guest` | Guest → Full account |

### 🏠 HOSTS/DISCOVER — `/api/v1/hosts`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/hosts/discover` | Home screen hosts (filters: interest, gender, level, sort_by, page) |
| GET | `/hosts/featured` | Featured hosts for banner |
| GET | `/hosts/online` | Currently online hosts |
| GET | `/hosts/{id}` | Single host detail |
| POST | `/hosts/admin/add` | Admin: Add host (form-data) |
| PUT | `/hosts/admin/{id}` | Admin: Update host |
| DELETE | `/hosts/admin/{id}` | Admin: Delete host |
| GET | `/hosts/admin/list/all` | Admin: All hosts list |

### 📹 VIDEO CALLS — `/api/v1/calls`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/calls/initiate` | Start call with host `{"host_id": "..."}` |
| POST | `/calls/answer/{call_id}` | Mark call as answered |
| POST | `/calls/billing-check` | **Call every 60 sec** — deducts coins, returns continue/end_call |
| POST | `/calls/end` | End call, add rating |
| GET | `/calls/random-host` | Get random incoming call (simulate) |
| GET | `/calls/history` | User's call history |
| GET | `/calls/admin/all` | Admin: All calls |

#### 💡 Call Billing Flow:
```
1. POST /calls/initiate  → get call_id
2. POST /calls/answer/{call_id}  → call starts
3. Every 60 seconds → POST /calls/billing-check {"call_id": "..."}
   - Response: {"action": "continue"} or {"action": "end_call", "reason": "insufficient_balance"}
4. POST /calls/end {"call_id": "...", "rating": 5}
```

### 💰 WALLET — `/api/v1/wallet`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/wallet/balance` | Current balance |
| GET | `/wallet/packages` | Coin packages list |
| POST | `/wallet/recharge` | Recharge wallet `{"amount": 199, "payment_method": "upi"}` |
| GET | `/wallet/transactions` | Transaction history |
| POST | `/wallet/admin/credit` | Admin: Credit coins to user |
| GET | `/wallet/admin/all-transactions` | Admin: All transactions |

#### 💳 Coin Packages:
| Price | Coins | Bonus |
|-------|-------|-------|
| ₹49 | 50 | 0 |
| ₹89 | 100 | +10 |
| ₹199 | 250 | +30 |
| ₹379 | 500 | +75 |
| ₹699 | 1000 | +200 |
| ₹1299 | 2000 | +500 |

### 🎁 GIFTS — `/api/v1/gifts`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/gifts/list` | All available gifts |
| GET | `/gifts/categories` | Gifts grouped by category |
| POST | `/gifts/send` | Send gift `{"gift_id":"...", "host_id":"...", "call_id":"...", "message":"..."}` |
| GET | `/gifts/my-history` | My gift sending history |
| POST | `/gifts/admin/add` | Admin: Add new gift |
| PUT | `/gifts/admin/{id}` | Admin: Update gift |
| GET | `/gifts/admin/stats` | Admin: Gift statistics |

### 🤖 CHAT BOT & RANDOM MATCH — `/api/v1/chat`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/bot/message` | Chat with Hinglish bot Priya `{"message": "Heyy!", "conversation_id": null}` |
| GET | `/chat/bot/history/{conv_id}` | Get chat history |
| GET | `/chat/bot/my-conversations` | All bot conversations |
| POST | `/chat/bot/new-session` | Start fresh chat session |
| POST | `/chat/random-match` | Random match with host `{"interest": "Music"}` |
| GET | `/chat/random-match/interests` | Popular interests for filter |

### ⭐ LEVELS & XP — `/api/v1/levels`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/levels/my-level` | My current level, XP, perks |
| GET | `/levels/leaderboard` | Top users by XP |
| GET | `/levels/all-levels` | All level details |

### 👮 ADMIN — `/api/v1/admin`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/login` | `{"username":"admin","password":"Admin@123"}` |
| GET | `/admin/dashboard` | Complete stats summary |
| GET | `/admin/users` | All users (search, filter, pagination) |
| GET | `/admin/users/{id}` | User detail with stats |
| POST | `/admin/users/block` | Block user |
| POST | `/admin/users/unblock/{id}` | Unblock user |
| DELETE | `/admin/users/{id}` | Delete user |
| GET | `/admin/analytics?days=30` | Analytics over time |
| POST | `/admin/notifications/send` | Send notification |
| GET | `/admin/notifications` | All notifications |

---

## 🏗 XP Actions (Auto Level System)

| Action | XP Gained |
|--------|-----------|
| Video call karna | +10 XP |
| Gift bhejna | +15 XP |
| Bot se chat | +1 XP |
| Daily login | +5 XP |
| Profile complete | +50 XP |
| Call receive | +5 XP |
| Gift receive | +8 XP |

## 🎯 Levels

| Level | Title | XP Required |
|-------|-------|-------------|
| 1 | Newcomer 🌱 | 0 |
| 2 | Explorer 🗺️ | 100 |
| 3 | Regular ⭐ | 300 |
| 4 | Active 🔥 | 600 |
| 5 | Popular 💫 | 1000 |
| 6 | Star 🌟 | 1500 |
| 7 | Super Star 🏆 | 2200 |
| 8 | Legend 👑 | 3000 |
| 9 | Elite 💎 | 4000 |
| 10 | Champion 🎖️ | 5500 |

---

## 📁 Project Structure

```
videocall-app/
├── main.py                 # FastAPI app entry point
├── requirements.txt
├── .env                    # Config (MongoDB URL, secret key)
├── start.sh               # Quick start script
├── admin/
│   └── index.html         # Complete Admin Panel
├── static/
│   └── uploads/           # Media files
└── app/
    ├── core/
    │   ├── config.py      # Settings
    │   ├── database.py    # MongoDB connection
    │   └── security.py    # JWT auth
    ├── routers/
    │   ├── auth.py        # Login/Register
    │   ├── hosts.py       # Host users/Discover
    │   ├── calls.py       # Video calls + billing
    │   ├── wallet.py      # Wallet system
    │   ├── gifts.py       # Gift module
    │   ├── chat.py        # Bot + random match
    │   ├── admin.py       # Admin APIs
    │   └── levels.py      # XP/Levels
    └── utils/
        └── helpers.py     # Utilities
```

## ⚙️ Environment Variables (.env)

```
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=videocall_app
SECRET_KEY=your-secret-key-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin@123
```
