from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime
from bson import ObjectId
from typing import Optional, List
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.utils.helpers import serialize_doc, calculate_level, add_xp_for_action
from app.routers.wallet import deduct_wallet

router = APIRouter(prefix="/gifts", tags=["Gifts"])

class SendGiftRequest(BaseModel):
    gift_id: str
    host_id: str
    call_id: Optional[str] = None
    message: Optional[str] = None

class AddGiftRequest(BaseModel):
    name: str
    emoji: str
    coins: int
    category: str = "standard"
    animation: Optional[str] = None
    is_active: bool = True

# Default gifts - admin can add more
DEFAULT_GIFTS = [
    {"name": "Rose", "emoji": "🌹", "coins": 5, "category": "flowers", "animation": "float"},
    {"name": "Heart", "emoji": "❤️", "coins": 10, "category": "love", "animation": "pulse"},
    {"name": "Kiss", "emoji": "💋", "coins": 15, "category": "love", "animation": "pop"},
    {"name": "Diamond", "emoji": "💎", "coins": 50, "category": "luxury", "animation": "sparkle"},
    {"name": "Crown", "emoji": "👑", "coins": 100, "category": "luxury", "animation": "glow"},
    {"name": "Bouquet", "emoji": "💐", "coins": 25, "category": "flowers", "animation": "float"},
    {"name": "Chocolate", "emoji": "🍫", "coins": 20, "category": "food", "animation": "bounce"},
    {"name": "Cake", "emoji": "🎂", "coins": 30, "category": "food", "animation": "bounce"},
    {"name": "Trophy", "emoji": "🏆", "coins": 200, "category": "premium", "animation": "shine"},
    {"name": "Rocket", "emoji": "🚀", "coins": 75, "category": "fun", "animation": "fly"},
    {"name": "Star", "emoji": "⭐", "coins": 40, "category": "standard", "animation": "twinkle"},
    {"name": "Rainbow", "emoji": "🌈", "coins": 60, "category": "premium", "animation": "wave"},
    {"name": "Fire", "emoji": "🔥", "coins": 35, "category": "fun", "animation": "burn"},
    {"name": "Unicorn", "emoji": "🦄", "coins": 150, "category": "premium", "animation": "magic"},
    {"name": "Sports Car", "emoji": "🏎️", "coins": 500, "category": "super", "animation": "zoom"},
    {"name": "Yacht", "emoji": "🛥️", "coins": 1000, "category": "super", "animation": "sail"},
]

async def ensure_default_gifts(db):
    count = await db.gifts.count_documents({})
    if count == 0:
        for gift in DEFAULT_GIFTS:
            gift["is_active"] = True
            gift["created_at"] = datetime.utcnow()
            gift["total_sent"] = 0
        await db.gifts.insert_many(DEFAULT_GIFTS)

@router.get("/list")
async def list_gifts(db=Depends(get_db)):
    """Get all available gifts"""
    await ensure_default_gifts(db)
    gifts = await db.gifts.find({"is_active": True}).sort("coins", 1).to_list(100)
    return {"success": True, "gifts": [serialize_doc(g) for g in gifts]}

@router.get("/categories")
async def get_gift_categories(db=Depends(get_db)):
    """Get gifts grouped by category"""
    await ensure_default_gifts(db)
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$category", "gifts": {"$push": "$$ROOT"}}},
        {"$sort": {"_id": 1}}
    ]
    result = await db.gifts.aggregate(pipeline).to_list(20)
    categories = []
    for cat in result:
        categories.append({
            "category": cat["_id"],
            "gifts": [serialize_doc(g) for g in cat["gifts"]]
        })
    return {"success": True, "categories": categories}

@router.post("/send")
async def send_gift(
    request: SendGiftRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Send a gift to a host during or outside call"""
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot send gifts. Please register.")

    # Get gift
    try:
        gift = await db.gifts.find_one({"_id": ObjectId(request.gift_id), "is_active": True})
    except:
        raise HTTPException(status_code=400, detail="Invalid gift ID")
    if not gift:
        raise HTTPException(status_code=404, detail="Gift not found")

    # Get host
    try:
        host = await db.host_users.find_one({"_id": ObjectId(request.host_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid host ID")
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    # Deduct from wallet
    result = await deduct_wallet(
        current_user["_id"],
        gift["coins"],
        f"Gift: {gift['name']} {gift['emoji']} to {host['name']}",
        db
    )

    if not result["success"]:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient balance. Gift costs {gift['coins']} coins. Your balance: {current_user.get('wallet_balance', 0)}"
        )

    # Record gift
    gift_sent_doc = {
        "sender_id": str(current_user["_id"]),
        "sender_name": current_user["name"],
        "host_id": str(host["_id"]),
        "host_name": host["name"],
        "gift_id": str(gift["_id"]),
        "gift_name": gift["name"],
        "gift_emoji": gift["emoji"],
        "coins": gift["coins"],
        "call_id": request.call_id,
        "message": request.message,
        "animation": gift.get("animation", "pop"),
        "created_at": datetime.utcnow()
    }
    await db.gift_logs.insert_one(gift_sent_doc)

    # Update gift send count
    await db.gifts.update_one({"_id": gift["_id"]}, {"$inc": {"total_sent": 1}})

    # Update user stats + XP
    xp_gained = add_xp_for_action("gift_sent")
    new_xp = current_user.get("xp", 0) + xp_gained
    level_info = calculate_level(new_xp)
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {"xp": new_xp, "level": level_info["level"], "level_title": level_info["title"]},
            "$inc": {"gifts_sent": 1}
        }
    )

    return {
        "success": True,
        "message": f"🎁 {gift['name']} {gift['emoji']} sent to {host['name']}!",
        "gift": serialize_doc(gift),
        "coins_spent": gift["coins"],
        "new_balance": result["new_balance"],
        "animation": gift.get("animation", "pop"),
        "xp_gained": xp_gained
    }

@router.get("/my-history")
async def my_gift_history(
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Get gift sending history"""
    gifts = await db.gift_logs.find(
        {"sender_id": str(current_user["_id"])}
    ).sort("created_at", -1).limit(50).to_list(50)
    return {"success": True, "gifts": [serialize_doc(g) for g in gifts]}

# ========== ADMIN ==========

@router.post("/admin/add")
async def admin_add_gift(
    request: AddGiftRequest,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: Add new gift"""
    gift_doc = {
        "name": request.name,
        "emoji": request.emoji,
        "coins": request.coins,
        "category": request.category,
        "animation": request.animation or "pop",
        "is_active": request.is_active,
        "total_sent": 0,
        "created_at": datetime.utcnow()
    }
    result = await db.gifts.insert_one(gift_doc)
    gift_doc["_id"] = result.inserted_id
    return {"success": True, "message": "Gift added", "gift": serialize_doc(gift_doc)}

@router.put("/admin/{gift_id}")
async def admin_update_gift(
    gift_id: str,
    name: Optional[str] = None,
    coins: Optional[int] = None,
    is_active: Optional[bool] = None,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    update_data = {}
    if name: update_data["name"] = name
    if coins is not None: update_data["coins"] = coins
    if is_active is not None: update_data["is_active"] = is_active
    try:
        await db.gifts.update_one({"_id": ObjectId(gift_id)}, {"$set": update_data})
    except:
        raise HTTPException(status_code=400, detail="Invalid gift ID")
    return {"success": True, "message": "Gift updated"}

@router.get("/admin/stats")
async def admin_gift_stats(db=Depends(get_db), admin=Depends(get_current_admin)):
    """Admin: Gift statistics"""
    pipeline = [
        {"$group": {
            "_id": "$gift_name",
            "total_sent": {"$sum": 1},
            "total_coins": {"$sum": "$coins"},
            "emoji": {"$first": "$gift_emoji"}
        }},
        {"$sort": {"total_sent": -1}},
        {"$limit": 20}
    ]
    stats = await db.gift_logs.aggregate(pipeline).to_list(20)
    total_gifts = await db.gift_logs.count_documents({})
    total_coins = await db.gift_logs.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$coins"}}}
    ]).to_list(1)

    return {
        "success": True,
        "top_gifts": stats,
        "total_gifts_sent": total_gifts,
        "total_coins_from_gifts": total_coins[0]["total"] if total_coins else 0
    }
