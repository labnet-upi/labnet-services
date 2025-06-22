# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import user, tugas_besar, inventaris
import uvicorn

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(user.router, prefix="/user", tags=["User"])
app.include_router(tugas_besar.router, prefix="/tugas_besar", tags=["Tubes"])
app.include_router(inventaris.router, prefix="/inventaris", tags=["Inventaris"])

# @app.on_event("startup")
# async def startup():
#     await init_indexes()

@app.get("/")
def read_root():
    return {"message": "Welcome to Main Service API"}