from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional, List
import os, aiofiles, uuid

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin, get_optional_user
from app.utils.helpers import serialize_doc

router = APIRouter(prefix="/hosts", tags=["Host Users - Discover"])

UPLOAD_DIR_PIC = "static/uploads/hosts/pics"
UPLOAD_DIR_VID = "static/uploads/hosts/videos"
os.makedirs(UPLOAD_DIR_PIC, exist_ok=True)
os.makedirs(UPLOAD_DIR_VID, exist_ok=True)

# ========== PUBLIC / USER ENDPOINTS ==========

@router.get("/discover")
async def discover_hosts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    interest: Optional[str] = None,
    gender: Optional[str] = None,
    level: Optional[int] = None,
    sort_by: str = Query("created_at", enum=["created_at", "price_per_minute", "level", "name"]),
    db=Depends(get_db),
    current_user=Depends(get_optional_user)
):
    """Home screen - Discover hosts (admin-added users)"""
    query = {"is_active": True}
    if interest:
        query["interests"] = {"$in": [interest]}
    if gender:
        query["gender"] = gender
    if level:
        query["level"] = level

    skip = (page - 1) * limit
    sort_dir = -1 if sort_by == "created_at" else 1

    hosts = await db.host_users.find(query).sort(sort_by, sort_dir).skip(skip).limit(limit).to_list(limit)
    total = await db.host_users.count_documents(query)

    return {
        "success": True,
        "hosts": [serialize_doc(h) for h in hosts],
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit,
        "has_next": (page * limit) < total
    }

@router.get("/featured")
async def get_featured_hosts(db=Depends(get_db)):
    """Get featured/top hosts for banner"""
    hosts = await db.host_users.find({"is_active": True, "is_featured": True}).limit(10).to_list(10)
    return {"success": True, "hosts": [serialize_doc(h) for h in hosts]}

@router.get("/online")
async def get_online_hosts(db=Depends(get_db)):
    """Get currently online/available hosts"""
    hosts = await db.host_users.find({"is_active": True, "is_online": True}).to_list(50)
    return {"success": True, "hosts": [serialize_doc(h) for h in hosts], "count": len(hosts)}

@router.get("/{host_id}")
async def get_host_detail(host_id: str, db=Depends(get_db)):
    """Get single host details"""
    try:
        host = await db.host_users.find_one({"_id": ObjectId(host_id), "is_active": True})
    except:
        raise HTTPException(status_code=400, detail="Invalid host ID")
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    return {"success": True, "host": serialize_doc(host)}

# ========== ADMIN ENDPOINTS ==========

@router.post("/admin/add")
async def admin_add_host(
    name: str = Form(...),
    age: int = Form(...),
    gender: str = Form("female"),
    level: int = Form(1),
    price_per_minute: float = Form(10.0),
    bio: Optional[str] = Form(None),
    interests: Optional[str] = Form(None),
    language: Optional[str] = Form("Hindi, English"),
    profile_picture: Optional[UploadFile] = File(None),
    preview_video: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: Add new host user"""
    pic_url = None
    if profile_picture and profile_picture.filename:
        ext = profile_picture.filename.split(".")[-1].lower()
        if ext not in ["jpg", "jpeg", "png", "webp"]:
            raise HTTPException(status_code=400, detail="Invalid image format")
        filename = f"{uuid.uuid4()}.{ext}"
        async with aiofiles.open(f"{UPLOAD_DIR_PIC}/{filename}", "wb") as f:
            await f.write(await profile_picture.read())
        pic_url = f"/static/uploads/hosts/pics/{filename}"

    video_url = None
    if preview_video and preview_video.filename:
        ext = preview_video.filename.split(".")[-1].lower()
        if ext not in ["mp4", "webm", "mov"]:
            raise HTTPException(status_code=400, detail="Invalid video format")
        filename = f"{uuid.uuid4()}.{ext}"
        async with aiofiles.open(f"{UPLOAD_DIR_VID}/{filename}", "wb") as f:
            await f.write(await preview_video.read())
        video_url = f"/static/uploads/hosts/videos/{filename}"

    levels_map = {1: "Newcomer", 2: "Explorer", 3: "Regular", 4: "Active", 5: "Popular",
                  6: "Star", 7: "Super Star", 8: "Legend", 9: "Elite", 10: "Champion"}

    host_doc = {
        "name": name,
        "age": age,
        "gender": gender,
        "level": level,
        "level_title": levels_map.get(level, "Newcomer"),
        "price_per_minute": price_per_minute,
        "bio": bio or f"Hi! I'm {name}. Let's have a great conversation!",
        "interests": [i.strip() for i in interests.split(",")] if interests else [],
        "language": language,
        "profile_picture": pic_url,
        "preview_video": video_url,
        "is_active": True,
        "is_online": True,
        "is_featured": False,
        "total_calls": 0,
        "total_minutes": 0,
        "total_earnings": 0.0,
        "rating": 4.5,
        "review_count": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await db.host_users.insert_one(host_doc)
    host_doc["_id"] = result.inserted_id

    return {"success": True, "message": "Host added successfully", "host": serialize_doc(host_doc)}

@router.put("/admin/{host_id}")
async def admin_update_host(
    host_id: str,
    name: Optional[str] = Form(None),
    age: Optional[int] = Form(None),
    gender: Optional[str] = Form(None),
    level: Optional[int] = Form(None),
    price_per_minute: Optional[float] = Form(None),
    bio: Optional[str] = Form(None),
    interests: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    is_featured: Optional[bool] = Form(None),
    is_online: Optional[bool] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    preview_video: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: Update host details"""
    update_data = {"updated_at": datetime.utcnow()}
    
    if name: update_data["name"] = name
    if age: update_data["age"] = age
    if gender: update_data["gender"] = gender
    if level:
        levels_map = {1: "Newcomer", 2: "Explorer", 3: "Regular", 4: "Active", 5: "Popular",
                      6: "Star", 7: "Super Star", 8: "Legend", 9: "Elite", 10: "Champion"}
        update_data["level"] = level
        update_data["level_title"] = levels_map.get(level, "Newcomer")
    if price_per_minute is not None: update_data["price_per_minute"] = price_per_minute
    if bio: update_data["bio"] = bio
    if interests: update_data["interests"] = [i.strip() for i in interests.split(",")]
    if is_active is not None: update_data["is_active"] = is_active
    if is_featured is not None: update_data["is_featured"] = is_featured
    if is_online is not None: update_data["is_online"] = is_online

    if profile_picture and profile_picture.filename:
        ext = profile_picture.filename.split(".")[-1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        async with aiofiles.open(f"{UPLOAD_DIR_PIC}/{filename}", "wb") as f:
            await f.write(await profile_picture.read())
        update_data["profile_picture"] = f"/static/uploads/hosts/pics/{filename}"

    if preview_video and preview_video.filename:
        ext = preview_video.filename.split(".")[-1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        async with aiofiles.open(f"{UPLOAD_DIR_VID}/{filename}", "wb") as f:
            await f.write(await preview_video.read())
        update_data["preview_video"] = f"/static/uploads/hosts/videos/{filename}"

    try:
        await db.host_users.update_one({"_id": ObjectId(host_id)}, {"$set": update_data})
    except:
        raise HTTPException(status_code=400, detail="Invalid host ID")

    updated = await db.host_users.find_one({"_id": ObjectId(host_id)})
    return {"success": True, "message": "Host updated", "host": serialize_doc(updated)}

@router.delete("/admin/{host_id}")
async def admin_delete_host(host_id: str, db=Depends(get_db), admin=Depends(get_current_admin)):
    """Admin: Delete host"""
    try:
        result = await db.host_users.delete_one({"_id": ObjectId(host_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid host ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Host not found")
    return {"success": True, "message": "Host deleted"}

@router.get("/admin/list/all")
async def admin_list_hosts(
    page: int = 1,
    limit: int = 20,
    db=Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Admin: List all hosts"""
    skip = (page - 1) * limit
    hosts = await db.host_users.find().skip(skip).limit(limit).to_list(limit)
    total = await db.host_users.count_documents({})
    return {
        "success": True,
        "hosts": [serialize_doc(h) for h in hosts],
        "total": total
    }
