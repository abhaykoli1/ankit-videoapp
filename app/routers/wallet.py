from fastapi import APIRouter, HTTPException, Depends, Body, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional, List
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.utils.helpers import serialize_doc

router = APIRouter(prefix="/wallet", tags=["Wallet"])

class RechargeRequest(BaseModel):
    amount: float
    payment_method: str = "upi"
    transaction_ref: Optional[str] = None

class AdminCreditRequest(BaseModel):
    user_id: str
    amount: float
    reason: str = "Admin Credit"

# Coin packages
COIN_PACKAGES = [
    {"id": "pack_50", "coins": 50, "price": 49, "bonus": 0, "label": "Starter Pack"},
    {"id": "pack_100", "coins": 100, "price": 89, "bonus": 10, "label": "Basic Pack"},
    {"id": "pack_250", "coins": 250, "price": 199, "bonus": 30, "label": "Popular Pack"},
    {"id": "pack_500", "coins": 500, "price": 379, "bonus": 75, "label": "Value Pack"},
    {"id": "pack_1000", "coins": 1000, "price": 699, "bonus": 200, "label": "Mega Pack"},
    {"id": "pack_2000", "coins": 2000, "price": 1299, "bonus": 500, "label": "Super Pack"},
]

@router.get("/balance")
async def get_wallet_balance(current_user=Depends(get_current_user), db=Depends(get_db)):
    """Get user wallet balance"""
    user = await db.users.find_one({"_id": current_user["_id"]})
    return {
        "success": True,
        "balance": user.get("wallet_balance", 0),
        "currency": "coins",
        "user_id": str(user["_id"])
    }

@router.get("/packages")
async def get_coin_packages():
    """Get available coin/recharge packages"""
    return {"success": True, "packages": COIN_PACKAGES}

@router.post("/recharge")
async def recharge_wallet(
    request: RechargeRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Recharge wallet - add coins"""
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot recharge. Please register first.")

    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    # Find matching package for bonus
    bonus = 0
    coins_to_add = request.amount
    for pack in COIN_PACKAGES:
        if pack["price"] == request.amount:
            coins_to_add = pack["coins"] + pack["bonus"]
            bonus = pack["bonus"]
            break

    new_balance = current_user.get("wallet_balance", 0) + coins_to_add

    txn_doc = {
        "user_id": str(current_user["_id"]),
        "type": "credit",
        "amount": coins_to_add,
        "base_amount": request.amount,
        "bonus_coins": bonus,
        "payment_method": request.payment_method,
        "transaction_ref": request.transaction_ref or f"TXN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "description": f"Wallet Recharge - ₹{request.amount}",
        "status": "success",
        "balance_before": current_user.get("wallet_balance", 0),
        "balance_after": new_balance,
        "created_at": datetime.utcnow()
    }

    await db.transactions.insert_one(txn_doc)
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"wallet_balance": new_balance}}
    )

    return {
        "success": True,
        "message": f"Wallet recharged! {coins_to_add} coins added ({bonus} bonus coins)",
        "coins_added": coins_to_add,
        "bonus_coins": bonus,
        "new_balance": new_balance
    }

@router.get("/transactions")
async def get_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    txn_type: Optional[str] = Query(None, enum=["credit", "debit"]),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Get transaction history"""
    query = {"user_id": str(current_user["_id"])}
    if txn_type:
        query["type"] = txn_type

    skip = (page - 1) * limit
    txns = await db.transactions.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.transactions.count_documents(query)

    return {
        "success": True,
        "transactions": [serialize_doc(t) for t in txns],
        "total": total,
        "page": page
    }

async def deduct_wallet(user_id: ObjectId, amount: float, description: str, db) -> dict:
    """Internal function to deduct wallet balance"""
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return {"success": False, "reason": "user_not_found"}

    current_balance = user.get("wallet_balance", 0)
    if current_balance < amount:
        return {"success": False, "reason": "insufficient_balance", "balance": current_balance}

    new_balance = current_balance - amount
    await db.users.update_one({"_id": user_id}, {"$set": {"wallet_balance": new_balance}})

    await db.transactions.insert_one({
        "user_id": str(user_id),
        "type": "debit",
        "amount": amount,
        "description": description,
        "status": "success",
        "balance_before": current_balance,
        "balance_after": new_balance,
        "created_at": datetime.utcnow()
    })

    return {"success": True, "new_balance": new_balance, "deducted": amount}

# ========== ADMIN WALLET APIs ==========

@router.post("/admin/credit")
async def admin_credit_user(
    request: AdminCreditRequest,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: Credit coins to user"""
    try:
        user = await db.users.find_one({"_id": ObjectId(request.user_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_balance = user.get("wallet_balance", 0) + request.amount
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"wallet_balance": new_balance}})
    await db.transactions.insert_one({
        "user_id": request.user_id,
        "type": "credit",
        "amount": request.amount,
        "description": f"Admin Credit: {request.reason}",
        "status": "success",
        "balance_before": user.get("wallet_balance", 0),
        "balance_after": new_balance,
        "created_at": datetime.utcnow()
    })
    return {"success": True, "message": f"{request.amount} coins credited", "new_balance": new_balance}

@router.get("/admin/all-transactions")
async def admin_all_transactions(
    page: int = 1,
    limit: int = 20,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: View all transactions"""
    skip = (page - 1) * limit
    txns = await db.transactions.find().sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.transactions.count_documents({})

    # Calculate stats
    pipeline = [
        {"$group": {"_id": "$type", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
    ]
    stats = await db.transactions.aggregate(pipeline).to_list(10)
    stats_dict = {s["_id"]: {"total": s["total"], "count": s["count"]} for s in stats}

    return {
        "success": True,
        "transactions": [serialize_doc(t) for t in txns],
        "total": total,
        "stats": stats_dict
    }
