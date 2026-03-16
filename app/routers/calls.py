from fastapi import APIRouter, HTTPException, Depends, Body, Query
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional
from pydantic import BaseModel
import asyncio, random, uuid

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.utils.helpers import serialize_doc, calculate_level, add_xp_for_action
from app.routers.wallet import deduct_wallet

router = APIRouter(prefix="/calls", tags=["Video Calls"])

class StartCallRequest(BaseModel):
    host_id: str

class EndCallRequest(BaseModel):
    call_id: str
    rating: Optional[int] = None
    review: Optional[str] = None

class BalanceCheckRequest(BaseModel):
    call_id: str

@router.post("/initiate")
async def initiate_call(
    request: StartCallRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Initiate a video call with a host"""
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot make calls. Please register.")

    # Check host exists
    try:
        host = await db.host_users.find_one({"_id": ObjectId(request.host_id), "is_active": True})
    except:
        raise HTTPException(status_code=400, detail="Invalid host ID")
    if not host:
        raise HTTPException(status_code=404, detail="Host not found or inactive")

    if not host.get("is_online", False):
        raise HTTPException(status_code=400, detail="Host is currently offline")

    # Check wallet - must have at least 1 minute worth
    min_required = host["price_per_minute"]
    user_balance = current_user.get("wallet_balance", 0)
    if user_balance < min_required:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient balance. You need at least {min_required} coins for a 1-minute call. Your balance: {user_balance} coins"
        )

    # Create call session
    call_doc = {
        "call_id": str(uuid.uuid4()),
        "caller_id": str(current_user["_id"]),
        "caller_name": current_user["name"],
        "host_id": str(host["_id"]),
        "host_name": host["name"],
        "price_per_minute": host["price_per_minute"],
        "status": "initiated",  # initiated -> ringing -> active -> ended
        "start_time": None,
        "end_time": None,
        "duration_seconds": 0,
        "total_cost": 0.0,
        "balance_at_start": user_balance,
        "last_billing_check": datetime.utcnow(),
        "rating": None,
        "review": None,
        "created_at": datetime.utcnow()
    }

    result = await db.call_logs.insert_one(call_doc)
    call_doc["_id"] = result.inserted_id

    return {
        "success": True,
        "message": "Call initiated. Connecting...",
        "call": serialize_doc(call_doc),
        "call_id": call_doc["call_id"],
        "your_balance": user_balance,
        "price_per_minute": host["price_per_minute"],
        "estimated_max_minutes": int(user_balance / host["price_per_minute"])
    }

@router.post("/answer/{call_id}")
async def answer_call(call_id: str, db=Depends(get_db)):
    """Mark call as answered/active"""
    call = await db.call_logs.find_one({"call_id": call_id})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    now = datetime.utcnow()
    await db.call_logs.update_one(
        {"call_id": call_id},
        {"$set": {"status": "active", "start_time": now, "last_billing_check": now}}
    )
    return {"success": True, "message": "Call connected", "start_time": now.isoformat()}

@router.post("/billing-check")
async def billing_check(
    request: BalanceCheckRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Called every 60 seconds during call to deduct coins and check balance.
    App should call this every minute during active call.
    """
    call = await db.call_logs.find_one({"call_id": request.call_id, "status": "active"})
    if not call:
        return {"success": False, "action": "end_call", "reason": "Call not found or already ended"}

    if str(current_user["_id"]) != call["caller_id"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    price_per_minute = call["price_per_minute"]

    # Deduct 1 minute cost
    result = await deduct_wallet(
        current_user["_id"],
        price_per_minute,
        f"Video Call - {call['host_name']} (1 min)",
        db
    )

    if not result["success"]:
        # Insufficient balance - end call
        await db.call_logs.update_one(
            {"call_id": request.call_id},
            {"$set": {"status": "ended_insufficient_balance", "end_time": datetime.utcnow()}}
        )
        return {
            "success": False,
            "action": "end_call",
            "reason": "insufficient_balance",
            "balance": result.get("balance", 0)
        }

    # Update call duration
    await db.call_logs.update_one(
        {"call_id": request.call_id},
        {
            "$inc": {"duration_seconds": 60, "total_cost": price_per_minute},
            "$set": {"last_billing_check": datetime.utcnow()}
        }
    )

    new_balance = result["new_balance"]
    can_continue = new_balance >= price_per_minute

    return {
        "success": True,
        "action": "continue" if can_continue else "end_call",
        "deducted": price_per_minute,
        "new_balance": new_balance,
        "reason": None if can_continue else "balance_will_run_out_next_minute",
        "warning": None if new_balance > price_per_minute * 2 else f"Low balance! Only {int(new_balance / price_per_minute)} minute(s) remaining"
    }

@router.post("/end")
async def end_call(
    request: EndCallRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """End a video call"""
    call = await db.call_logs.find_one({"call_id": request.call_id})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if str(current_user["_id"]) != call["caller_id"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if call["status"] not in ["active", "initiated", "ringing"]:
        return {"success": False, "message": "Call already ended"}

    end_time = datetime.utcnow()
    duration_secs = call.get("duration_seconds", 0)
    if call.get("start_time"):
        actual_secs = (end_time - call["start_time"]).seconds
        duration_secs = max(duration_secs, actual_secs)

    update_data = {
        "status": "completed",
        "end_time": end_time,
        "duration_seconds": duration_secs,
    }
    if request.rating:
        update_data["rating"] = max(1, min(5, request.rating))
    if request.review:
        update_data["review"] = request.review

    await db.call_logs.update_one({"call_id": request.call_id}, {"$set": update_data})

    # Update XP for caller
    xp_gained = add_xp_for_action("call_made")
    new_xp = current_user.get("xp", 0) + xp_gained
    level_info = calculate_level(new_xp)
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "xp": new_xp,
                "level": level_info["level"],
                "level_title": level_info["title"]
            },
            "$inc": {"call_count": 1, "total_call_minutes": duration_secs // 60}
        }
    )

    # Update host stats
    total_cost = call.get("total_cost", 0)
    await db.host_users.update_one(
        {"_id": ObjectId(call["host_id"])},
        {"$inc": {"total_calls": 1, "total_minutes": duration_secs // 60, "total_earnings": total_cost}}
    )

    # Update host rating if provided
    if request.rating:
        host = await db.host_users.find_one({"_id": ObjectId(call["host_id"])})
        if host:
            old_rating = host.get("rating", 4.5)
            count = host.get("review_count", 0)
            new_rating = ((old_rating * count) + request.rating) / (count + 1)
            await db.host_users.update_one(
                {"_id": ObjectId(call["host_id"])},
                {"$set": {"rating": round(new_rating, 1)}, "$inc": {"review_count": 1}}
            )

    return {
        "success": True,
        "message": "Call ended",
        "duration_seconds": duration_secs,
        "duration_minutes": round(duration_secs / 60, 1),
        "total_cost": total_cost,
        "xp_gained": xp_gained,
        "level_info": level_info
    }

@router.get("/random-host")
async def get_random_incoming_call(
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Simulate random incoming call from admin-added hosts"""
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot receive calls")

    online_hosts = await db.host_users.find({"is_active": True, "is_online": True}).to_list(100)
    if not online_hosts:
        return {"success": False, "message": "No hosts available right now"}

    host = random.choice(online_hosts)
    return {
        "success": True,
        "incoming_call": True,
        "host": serialize_doc(host),
        "message": f"{host['name']} is calling you!",
        "price_per_minute": host["price_per_minute"]
    }

@router.get("/history")
async def call_history(
    page: int = 1,
    limit: int = 20,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Get call history for current user"""
    skip = (page - 1) * limit
    calls = await db.call_logs.find(
        {"caller_id": str(current_user["_id"])}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.call_logs.count_documents({"caller_id": str(current_user["_id"])})

    return {
        "success": True,
        "calls": [serialize_doc(c) for c in calls],
        "total": total,
        "page": page
    }

@router.get("/admin/all")
async def admin_all_calls(
    page: int = 1,
    limit: int = 20,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: View all calls"""
    skip = (page - 1) * limit
    calls = await db.call_logs.find().sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.call_logs.count_documents({})

    # Stats
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {
            "_id": None,
            "total_calls": {"$sum": 1},
            "total_revenue": {"$sum": "$total_cost"},
            "avg_duration": {"$avg": "$duration_seconds"}
        }}
    ]
    stats_result = await db.call_logs.aggregate(pipeline).to_list(1)
    stats = stats_result[0] if stats_result else {}

    return {
        "success": True,
        "calls": [serialize_doc(c) for c in calls],
        "total": total,
        "stats": {
            "total_completed_calls": stats.get("total_calls", 0),
            "total_revenue": round(stats.get("total_revenue", 0), 2),
            "avg_duration_seconds": round(stats.get("avg_duration", 0), 0)
        }
    }
