import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, Request
from fastapi.security import APIKeyHeader
from database import db

# Konfigurasi session
SESSION_EXPIRE_MINUTES = 60 * 24  # 1 hari
SESSION_HEADER = "Authorization"

api_key_header = APIKeyHeader(name=SESSION_HEADER, auto_error=False)

async def create_session(user: dict) -> str:
    session_id = str(uuid.uuid4())
    session_data = {
        "_id": session_id,
        "user_id": str(user["_id"]),
        "nim": user["nim"],
        "role": user["role"],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
    }
    await db.sessions.insert_one(session_data)
    return session_id

async def get_current_user(session_id: str = Depends(api_key_header)):
    if not session_id:
        raise HTTPException(status_code=401, detail="No session provided")

    session = await db.sessions.find_one({"_id": session_id})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # Opsional: auto-extend session expiration
    if session["expires_at"] < datetime.utcnow():
        await db.sessions.delete_one({"_id": session_id})
        raise HTTPException(status_code=401, detail="Session expired")

    user = await db.users.find_one({"_id": session["user_id"]})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
