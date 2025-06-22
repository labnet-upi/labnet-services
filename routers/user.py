from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId

from database import db
from auth import get_current_user
import uuid
from datetime import datetime, timedelta

router = APIRouter()

# -------------------------------
# Data Models
# -------------------------------

class LoginRequest(BaseModel):
    nim: str

class UserCreate(BaseModel):
    name: str
    nim: str
    phone: Optional[str] = None
    role: str = "mahasiswa"  # bisa juga "asisten"

class UserOut(BaseModel):
    id: str
    name: str
    nim: str
    phone: Optional[str]
    role: str

class EditProfile(BaseModel):
    name: Optional[str]
    phone: Optional[str]

# -------------------------------
# Helper: Convert ObjectId ke str
# -------------------------------

def convert_objectid(doc):
    doc = dict(doc)
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc

# -------------------------------
# Routes
# -------------------------------

@router.post("/login")
async def login_user(login: LoginRequest):
    user = await db.users.find_one({"nim": login.nim})
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    # Buat session baru
    session_id = str(uuid.uuid4())
    session_data = {
        "_id": session_id,
        "user_id": str(user["_id"]),
        "nim": user["nim"],
        "role": user["role"],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=1)
    }
    await db.sessions.insert_one(session_data)

    return {
        "session_token": session_id,
        "user": convert_objectid(user)
    }

@router.post("/logout")
async def logout_user(current_user=Depends(get_current_user)):
    await db.sessions.delete_many({"user_id": str(current_user["_id"])})
    return {"message": "Logged out successfully"}

@router.post("/")
async def create_user(user: UserCreate):
    existing = await db.users.find_one({"nim": user.nim})
    if existing:
        raise HTTPException(status_code=400, detail="NIM sudah terdaftar")

    result = await db.users.insert_one(user.dict())
    new_user = await db.users.find_one({"_id": result.inserted_id})
    return convert_objectid(new_user)

@router.get("/me", response_model=UserOut)
async def get_profile(current_user=Depends(get_current_user)):
    return convert_objectid(current_user)

@router.put("/edit-profile")
async def edit_profile(data: EditProfile, current_user=Depends(get_current_user)):
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan")

    await db.users.update_one({"_id": current_user["_id"]}, {"$set": update_data})
    updated_user = await db.users.find_one({"_id": current_user["_id"]})
    return convert_objectid(updated_user)
