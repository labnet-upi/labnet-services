import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from database import db
from bson import ObjectId

# Konfigurasi session
SESSION_EXPIRE_MINUTES = 60 * 24  # 1 hari
SESSION_HEADER = "Authorization"

api_key_header = APIKeyHeader(name=SESSION_HEADER, auto_error=False)

async def create_session(user: dict) -> str:
    session_id = str(uuid.uuid4())
    session_data = {
        "_id": ObjectId(session_id),
        "user_id": ObjectId(user["_id"]),
        "nim": user["nim"],
        "role": user["role"],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
    }
    await db.sessions.insert_one(session_data)
    return session_id

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    session_id = credentials.credentials  # isi Bearer
    session = await db.sessions.find_one({"_id": session_id})
    # if not session or session["expires_at"] < datetime.utcnow():
    #     raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    # Kalau pakai ObjectId di user_id:
    user = await db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
