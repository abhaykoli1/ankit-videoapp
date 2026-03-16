from bson import ObjectId
from datetime import datetime
from typing import Any, Dict
import re
import random
import string

def serialize_doc(doc) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if key == "_id":
            result["id"] = str(value)
        elif isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, list):
            result[key] = [serialize_doc(item) if isinstance(item, dict) else (str(item) if isinstance(item, ObjectId) else item) for item in value]
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        else:
            result[key] = value
    return result

def generate_guest_username():
    suffix = ''.join(random.choices(string.digits, k=6))
    return f"guest_{suffix}"

def calculate_level(xp: int) -> dict:
    """Calculate user level based on XP"""
    levels = [
        {"level": 1, "title": "Newcomer", "min_xp": 0, "max_xp": 100},
        {"level": 2, "title": "Explorer", "min_xp": 100, "max_xp": 300},
        {"level": 3, "title": "Regular", "min_xp": 300, "max_xp": 600},
        {"level": 4, "title": "Active", "min_xp": 600, "max_xp": 1000},
        {"level": 5, "title": "Popular", "min_xp": 1000, "max_xp": 1500},
        {"level": 6, "title": "Star", "min_xp": 1500, "max_xp": 2200},
        {"level": 7, "title": "Super Star", "min_xp": 2200, "max_xp": 3000},
        {"level": 8, "title": "Legend", "min_xp": 3000, "max_xp": 4000},
        {"level": 9, "title": "Elite", "min_xp": 4000, "max_xp": 5500},
        {"level": 10, "title": "Champion", "min_xp": 5500, "max_xp": 999999},
    ]
    for lvl in reversed(levels):
        if xp >= lvl["min_xp"]:
            progress = ((xp - lvl["min_xp"]) / (lvl["max_xp"] - lvl["min_xp"])) * 100
            return {
                "level": lvl["level"],
                "title": lvl["title"],
                "xp": xp,
                "next_level_xp": lvl["max_xp"],
                "progress_percent": min(round(progress, 1), 100)
            }
    return {"level": 1, "title": "Newcomer", "xp": xp, "next_level_xp": 100, "progress_percent": 0}

def add_xp_for_action(action: str) -> int:
    """Return XP points for different actions"""
    xp_map = {
        "call_made": 10,
        "call_received": 5,
        "gift_sent": 15,
        "gift_received": 8,
        "chat_message": 1,
        "profile_complete": 50,
        "daily_login": 5,
    }
    return xp_map.get(action, 0)

def validate_mobile(mobile: str) -> bool:
    return bool(re.match(r'^[6-9]\d{9}$', mobile))
