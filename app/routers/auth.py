from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional
import os, aiofiles, uuid

from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, settings
)
from app.utils.helpers import serialize_doc, generate_guest_username, calculate_level, validate_mobile

router = APIRouter(prefix="/auth", tags=["Authentication"])

UPLOAD_DIR = "static/uploads/profiles"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/register")
async def register(
    name: str = Form(...),
    mobile: str = Form(...),
    password: str = Form(...),
    gender: str = Form("other"),
    profile_picture: Optional[UploadFile] = File(None),
    db=Depends(get_db)
):
    """Register new user with mobile number"""
    if not validate_mobile(mobile):
        raise HTTPException(status_code=400, detail="Invalid mobile number. Must be 10-digit Indian number.")
    
    existing = await db.users.find_one({"mobile": mobile})
    if existing:
        raise HTTPException(status_code=400, detail="Mobile number already registered")

    # Handle profile picture upload
    pic_url = None
    if profile_picture and profile_picture.filename:
        ext = profile_picture.filename.split(".")[-1].lower()
        if ext not in ["jpg", "jpeg", "png", "webp"]:
            raise HTTPException(status_code=400, detail="Only JPG/PNG/WEBP images allowed")
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = f"{UPLOAD_DIR}/{filename}"
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(await profile_picture.read())
        pic_url = f"/static/uploads/profiles/{filename}"

    user_doc = {
        "name": name,
        "mobile": mobile,
        "username": f"user_{mobile[-4:]}_{uuid.uuid4().hex[:4]}",
        "password": get_password_hash(password),
        "gender": gender,
        "profile_picture": pic_url,
        "wallet_balance": 0.0,
        "xp": 0,
        "level": 1,
        "level_title": "Newcomer",
        "is_blocked": False,
        "is_guest": False,
        "interests": [],
        "call_count": 0,
        "total_call_minutes": 0,
        "gifts_sent": 0,
        "gifts_received": 0,
        "created_at": datetime.utcnow(),
        "last_login": datetime.utcnow(),
        "daily_login_date": datetime.utcnow().date().isoformat()
    }

    result = await db.users.insert_one(user_doc)
    token = create_access_token({"sub": str(result.inserted_id)})

    user_doc["_id"] = result.inserted_id
    return {
        "success": True,
        "message": "Registration successful",
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_doc(user_doc)
    }

@router.post("/login")
async def login(
    mobile: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db)
):
    """Login with mobile and password"""
    user = await db.users.find_one({"mobile": mobile})
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid mobile or password")

    if user.get("is_blocked"):
        raise HTTPException(status_code=403, detail="Your account has been blocked. Contact support.")

    # Daily login XP bonus
    today = datetime.utcnow().date().isoformat()
    update_data = {"last_login": datetime.utcnow()}
    if user.get("daily_login_date") != today:
        new_xp = user.get("xp", 0) + 5
        level_info = calculate_level(new_xp)
        update_data.update({
            "daily_login_date": today,
            "xp": new_xp,
            "level": level_info["level"],
            "level_title": level_info["title"]
        })

    await db.users.update_one({"_id": user["_id"]}, {"$set": update_data})
    token = create_access_token({"sub": str(user["_id"])})

    return {
        "success": True,
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_doc(user)
    }

@router.post("/guest-login")
async def guest_login(db=Depends(get_db)):
    """Login as guest - limited features"""
    username = generate_guest_username()
    guest_doc = {
        "name": f"Guest {username[-6:]}",
        "username": username,
        "mobile": None,
        "password": None,
        "gender": "unknown",
        "profile_picture": None,
        "wallet_balance": 0.0,
        "xp": 0,
        "level": 1,
        "level_title": "Newcomer",
        "is_blocked": False,
        "is_guest": True,
        "interests": [],
        "call_count": 0,
        "total_call_minutes": 0,
        "gifts_sent": 0,
        "gifts_received": 0,
        "created_at": datetime.utcnow(),
        "last_login": datetime.utcnow(),
        "daily_login_date": datetime.utcnow().date().isoformat()
    }
    result = await db.users.insert_one(guest_doc)
    token = create_access_token({"sub": str(result.inserted_id)})
    guest_doc["_id"] = result.inserted_id

    return {
        "success": True,
        "message": "Guest login successful. Register to unlock all features.",
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_doc(guest_doc),
        "is_guest": True,
        "guest_limitations": ["Cannot make video calls", "Cannot send gifts", "Wallet not available"]
    }

@router.get("/me")
async def get_profile(current_user=Depends(get_current_user)):
    """Get current user profile"""
    return {"success": True, "user": serialize_doc(current_user)}

@router.put("/profile")
async def update_profile(
    name: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    interests: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Update user profile"""
    update_data = {}
    if name: update_data["name"] = name
    if gender: update_data["gender"] = gender
    if interests:
        update_data["interests"] = [i.strip() for i in interests.split(",")]

    if profile_picture and profile_picture.filename:
        ext = profile_picture.filename.split(".")[-1].lower()
        if ext not in ["jpg", "jpeg", "png", "webp"]:
            raise HTTPException(status_code=400, detail="Only JPG/PNG/WEBP images allowed")
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = f"{UPLOAD_DIR}/{filename}"
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(await profile_picture.read())
        update_data["profile_picture"] = f"/static/uploads/profiles/{filename}"

    if update_data:
        await db.users.update_one({"_id": current_user["_id"]}, {"$set": update_data})

    updated = await db.users.find_one({"_id": current_user["_id"]})
    return {"success": True, "message": "Profile updated", "user": serialize_doc(updated)}

@router.post("/convert-guest")
async def convert_guest_to_user(
    name: str = Form(...),
    mobile: str = Form(...),
    password: str = Form(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Convert guest account to full account"""
    if not current_user.get("is_guest"):
        raise HTTPException(status_code=400, detail="Account is already a full account")

    if not validate_mobile(mobile):
        raise HTTPException(status_code=400, detail="Invalid mobile number")

    existing = await db.users.find_one({"mobile": mobile})
    if existing:
        raise HTTPException(status_code=400, detail="Mobile already registered")

    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {
            "name": name,
            "mobile": mobile,
            "password": get_password_hash(password),
            "is_guest": False,
            "username": f"user_{mobile[-4:]}_{uuid.uuid4().hex[:4]}"
        }}
    )
    return {"success": True, "message": "Account converted successfully! You now have full access."}
