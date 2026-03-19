from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime

from app.core.database import get_db

router = APIRouter(prefix="/upid", tags=["Single UPID Module"])


@router.post("/add")
async def add_upid(
    upid: str = Body(...),
    db=Depends(get_db)
):
    existing = await db.upid_config.find_one({})

    if existing:
        raise HTTPException(status_code=400, detail="UPID already exists. Use update.")

    doc = {
        "upid": upid,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    await db.upid_config.insert_one(doc)

    return {
        "success": True,
        "message": "UPID created",
        "upid": upid
    }

@router.get("/get")
async def get_upid(db=Depends(get_db)):
    doc = await db.upid_config.find_one({})

    if not doc:
        raise HTTPException(status_code=404, detail="UPID not found")

    return {
        "success": True,
        "upid": doc["upid"]
    }

@router.put("/update")
async def update_upid(
    upid: str = Body(...),
    db=Depends(get_db)
):
    existing = await db.upid_config.find_one({})

    if not existing:
        raise HTTPException(status_code=404, detail="UPID not found. Create first.")

    await db.upid_config.update_one(
        {},
        {
            "$set": {
                "upid": upid,
                "updated_at": datetime.utcnow()
            }
        }
    )

    return {
        "success": True,
        "message": "UPID updated",
        "upid": upid
    }