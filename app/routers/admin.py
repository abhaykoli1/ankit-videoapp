from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_admin, get_password_hash, settings, create_admin_token
from app.utils.helpers import serialize_doc

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

class AdminLogin(BaseModel):
    username: str
    password: str

class BlockUserRequest(BaseModel):
    user_id: str
    reason: Optional[str] = "Violated terms of service"

class NotificationRequest(BaseModel):
    title: str
    message: str
    target: str = "all"  # all, specific_user
    user_id: Optional[str] = None

@router.post("/login")
async def admin_login(request: AdminLogin):
    """Admin login"""
    if request.username != settings.ADMIN_USERNAME or request.password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    token = create_admin_token()
    return {
        "success": True,
        "message": "Admin login successful",
        "access_token": token,
        "token_type": "bearer",
        "admin": {"username": settings.ADMIN_USERNAME, "role": "admin"}
    }

@router.get("/dashboard")
async def admin_dashboard(db=Depends(get_db), admin=Depends(get_current_admin)):
    """Admin dashboard - complete summary"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    # User stats
    total_users = await db.users.count_documents({})
    registered_users = await db.users.count_documents({"is_guest": False})
    guest_users = await db.users.count_documents({"is_guest": True})
    blocked_users = await db.users.count_documents({"is_blocked": True})
    new_today = await db.users.count_documents({"created_at": {"$gte": today_start}})
    new_this_week = await db.users.count_documents({"created_at": {"$gte": week_start}})
    new_this_month = await db.users.count_documents({"created_at": {"$gte": month_start}})

    # Host stats
    total_hosts = await db.host_users.count_documents({})
    active_hosts = await db.host_users.count_documents({"is_active": True})
    online_hosts = await db.host_users.count_documents({"is_online": True})

    # Call stats
    total_calls = await db.call_logs.count_documents({})
    completed_calls = await db.call_logs.count_documents({"status": "completed"})
    calls_today = await db.call_logs.count_documents({"created_at": {"$gte": today_start}})

    # Revenue
    revenue_pipeline = [
        {"$match": {"type": "credit", "status": "success"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
    ]
    revenue_result = await db.transactions.aggregate(revenue_pipeline).to_list(1)
    total_revenue_coins = revenue_result[0]["total"] if revenue_result else 0
    total_recharges = revenue_result[0]["count"] if revenue_result else 0

    today_revenue = await db.transactions.aggregate([
        {"$match": {"type": "credit", "status": "success", "created_at": {"$gte": today_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$base_amount"}}}
    ]).to_list(1)
    today_revenue_inr = today_revenue[0]["total"] if today_revenue else 0

    month_revenue = await db.transactions.aggregate([
        {"$match": {"type": "credit", "status": "success", "created_at": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$base_amount"}}}
    ]).to_list(1)
    month_revenue_inr = month_revenue[0]["total"] if month_revenue else 0

    # Gift stats
    total_gifts = await db.gift_logs.count_documents({})
    gifts_today = await db.gift_logs.count_documents({"created_at": {"$gte": today_start}})

    # Top users by balance
    top_users = await db.users.find(
        {"is_guest": False}
    ).sort("wallet_balance", -1).limit(5).to_list(5)

    return {
        "success": True,
        "dashboard": {
            "users": {
                "total": total_users,
                "registered": registered_users,
                "guests": guest_users,
                "blocked": blocked_users,
                "new_today": new_today,
                "new_this_week": new_this_week,
                "new_this_month": new_this_month
            },
            "hosts": {
                "total": total_hosts,
                "active": active_hosts,
                "online": online_hosts
            },
            "calls": {
                "total": total_calls,
                "completed": completed_calls,
                "today": calls_today,
                "completion_rate": f"{(completed_calls/total_calls*100):.1f}%" if total_calls > 0 else "0%"
            },
            "revenue": {
                "total_coins_recharged": total_revenue_coins,
                "total_recharge_transactions": total_recharges,
                "today_inr": today_revenue_inr,
                "this_month_inr": month_revenue_inr
            },
            "gifts": {
                "total_sent": total_gifts,
                "today": gifts_today
            },
            "top_users_by_balance": [
                {
                    "name": u.get("name"),
                    "mobile": u.get("mobile"),
                    "balance": u.get("wallet_balance", 0),
                    "id": str(u["_id"])
                } for u in top_users
            ]
        }
    }

@router.get("/users")
async def admin_get_users(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    is_blocked: Optional[bool] = None,
    is_guest: Optional[bool] = None,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: Get all users with filters"""
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"mobile": {"$regex": search, "$options": "i"}},
            {"username": {"$regex": search, "$options": "i"}}
        ]
    if is_blocked is not None:
        query["is_blocked"] = is_blocked
    if is_guest is not None:
        query["is_guest"] = is_guest

    skip = (page - 1) * limit
    users = await db.users.find(query, {"password": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.users.count_documents(query)

    return {
        "success": True,
        "users": [serialize_doc(u) for u in users],
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit
    }

@router.get("/users/{user_id}")
async def admin_get_user(user_id: str, db=Depends(get_db), admin=Depends(get_current_admin)):
    """Admin: Get specific user details"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get call count and spend
    call_count = await db.call_logs.count_documents({"caller_id": user_id})
    total_gifts = await db.gift_logs.count_documents({"sender_id": user_id})
    transactions = await db.transactions.find({"user_id": user_id}).sort("created_at", -1).limit(10).to_list(10)

    return {
        "success": True,
        "user": serialize_doc(user),
        "stats": {
            "calls_made": call_count,
            "gifts_sent": total_gifts,
        },
        "recent_transactions": [serialize_doc(t) for t in transactions]
    }

@router.post("/users/block")
async def admin_block_user(
    request: BlockUserRequest,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: Block a user"""
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(request.user_id)},
            {"$set": {"is_blocked": True, "block_reason": request.reason, "blocked_at": datetime.utcnow()}}
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": f"User blocked. Reason: {request.reason}"}

@router.post("/users/unblock/{user_id}")
async def admin_unblock_user(user_id: str, db=Depends(get_db), admin=Depends(get_current_admin)):
    """Admin: Unblock a user"""
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_blocked": False}, "$unset": {"block_reason": "", "blocked_at": ""}}
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": "User unblocked successfully"}

@router.delete("/users/{user_id}")
async def admin_delete_user(user_id: str, db=Depends(get_db), admin=Depends(get_current_admin)):
    """Admin: Delete user account"""
    try:
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": "User deleted"}

@router.get("/analytics")
async def admin_analytics(
    days: int = 30,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: Analytics over time"""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Daily new users
    user_pipeline = [
        {"$match": {"created_at": {"$gte": start_date}, "is_guest": False}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_users = await db.users.aggregate(user_pipeline).to_list(days)

    # Daily calls
    call_pipeline = [
        {"$match": {"created_at": {"$gte": start_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1},
            "revenue": {"$sum": "$total_cost"}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_calls = await db.call_logs.aggregate(call_pipeline).to_list(days)

    # Daily recharges
    recharge_pipeline = [
        {"$match": {"type": "credit", "created_at": {"$gte": start_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1},
            "amount": {"$sum": "$base_amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_recharges = await db.transactions.aggregate(recharge_pipeline).to_list(days)

    return {
        "success": True,
        "period_days": days,
        "analytics": {
            "daily_registrations": daily_users,
            "daily_calls": daily_calls,
            "daily_recharges": daily_recharges
        }
    }

@router.post("/notifications/send")
async def send_notification(
    request: NotificationRequest,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: Send notification to users"""
    notif_doc = {
        "title": request.title,
        "message": request.message,
        "target": request.target,
        "user_id": request.user_id,
        "sent_at": datetime.utcnow(),
        "sent_by": "admin"
    }
    await db.notifications.insert_one(notif_doc)
    return {"success": True, "message": "Notification sent successfully"}

@router.get("/notifications")
async def get_notifications(db=Depends(get_db), admin=Depends(get_current_admin)):
    """Admin: View sent notifications"""
    notifs = await db.notifications.find().sort("sent_at", -1).limit(50).to_list(50)
    return {"success": True, "notifications": [serialize_doc(n) for n in notifs]}
