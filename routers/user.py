from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List
from database import db
from bson import ObjectId

router = APIRouter()

class User(BaseModel):
    name: str
    email: EmailStr

class UserOut(User):
    id: str

@router.get("/", response_model=List[UserOut])
async def get_users():
    users_cursor = db.users.find()
    users = []
    async for user in users_cursor:
        user["id"] = str(user["_id"])
        users.append(UserOut(**user))
    return users

@router.post("/", response_model=UserOut)
async def create_user(user: User):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    result = await db.users.insert_one(user.dict())
    new_user = await db.users.find_one({"_id": result.inserted_id})
    new_user["id"] = str(new_user["_id"])
    return UserOut(**new_user)
