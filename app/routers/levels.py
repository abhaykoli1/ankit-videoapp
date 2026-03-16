from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.core.security import get_current_user
from app.utils.helpers import serialize_doc, calculate_level

router = APIRouter(prefix="/levels", tags=["User Levels & XP"])

LEVEL_DETAILS = [
    {"level": 1, "title": "Newcomer", "min_xp": 0, "max_xp": 100, "badge": "🌱", "perks": ["Basic chat access"]},
    {"level": 2, "title": "Explorer", "min_xp": 100, "max_xp": 300, "badge": "🗺️", "perks": ["Unlock Random Match"]},
    {"level": 3, "title": "Regular", "min_xp": 300, "max_xp": 600, "badge": "⭐", "perks": ["Priority in discover feed"]},
    {"level": 4, "title": "Active", "min_xp": 600, "max_xp": 1000, "badge": "🔥", "perks": ["5% bonus on recharge"]},
    {"level": 5, "title": "Popular", "min_xp": 1000, "max_xp": 1500, "badge": "💫", "perks": ["Access to premium hosts"]},
    {"level": 6, "title": "Star", "min_xp": 1500, "max_xp": 2200, "badge": "🌟", "perks": ["10% bonus on recharge", "Exclusive gifts unlocked"]},
    {"level": 7, "title": "Super Star", "min_xp": 2200, "max_xp": 3000, "badge": "🏆", "perks": ["VIP badge on profile"]},
    {"level": 8, "title": "Legend", "min_xp": 3000, "max_xp": 4000, "badge": "👑", "perks": ["15% bonus on recharge", "Legend frame"]},
    {"level": 9, "title": "Elite", "min_xp": 4000, "max_xp": 5500, "badge": "💎", "perks": ["Elite status", "20% bonus on recharge"]},
    {"level": 10, "title": "Champion", "min_xp": 5500, "max_xp": 999999, "badge": "🎖️", "perks": ["Champion frame", "25% bonus", "Top of discover feed"]},
]

XP_ACTIONS = [
    {"action": "call_made", "xp": 10, "description": "Video call karo"},
    {"action": "gift_sent", "xp": 15, "description": "Gift bhejo"},
    {"action": "chat_message", "xp": 1, "description": "Bot se baat karo"},
    {"action": "daily_login", "xp": 5, "description": "Roz login karo"},
    {"action": "profile_complete", "xp": 50, "description": "Profile complete karo"},
    {"action": "call_received", "xp": 5, "description": "Call receive karo"},
    {"action": "gift_received", "xp": 8, "description": "Gift receive karo"},
]

@router.get("/my-level")
async def get_my_level(current_user=Depends(get_current_user)):
    """Get current user's level and XP info"""
    xp = current_user.get("xp", 0)
    level_info = calculate_level(xp)
    
    current_level_detail = next(
        (l for l in LEVEL_DETAILS if l["level"] == level_info["level"]), 
        LEVEL_DETAILS[0]
    )
    
    return {
        "success": True,
        "level": level_info,
        "badge": current_level_detail["badge"],
        "perks": current_level_detail["perks"],
        "xp_actions": XP_ACTIONS
    }

@router.get("/leaderboard")
async def get_leaderboard(db=Depends(get_db)):
    """Top users by XP/Level"""
    top_users = await db.users.find(
        {"is_guest": False, "is_blocked": False},
        {"name": 1, "level": 1, "level_title": 1, "xp": 1, "profile_picture": 1}
    ).sort("xp", -1).limit(20).to_list(20)
    
    leaderboard = []
    for i, user in enumerate(top_users):
        leaderboard.append({
            "rank": i + 1,
            "name": user.get("name"),
            "level": user.get("level", 1),
            "level_title": user.get("level_title", "Newcomer"),
            "xp": user.get("xp", 0),
            "profile_picture": user.get("profile_picture"),
            "id": str(user["_id"])
        })
    
    return {"success": True, "leaderboard": leaderboard}

@router.get("/all-levels")
async def get_all_levels():
    """Get info about all levels"""
    return {"success": True, "levels": LEVEL_DETAILS, "xp_actions": XP_ACTIONS}
