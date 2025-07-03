from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.object_id_encoder_middleware import ObjectIdEncoderMiddleware
from routers import user, inventaris
from routers.tugas_besar import router as tugas_besar_router
from utils.database import db
from core.logger import logger

app = FastAPI()

origins = [
    "http://localhost:8080",      # Vue dev server default
    "http://127.0.0.1:8080",      # Vue dev server alternatif
    "http://localhost:8081",      # Vue di Docker (host)
    "http://127.0.0.1:8081",      # Vue di Docker (host)
]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ObjectIdEncoderMiddleware)

# Include routers
app.include_router(user.router, prefix="/user", tags=["User"])
app.include_router(tugas_besar_router, prefix="/tugas_besar", tags=["Tubes"])
app.include_router(inventaris.router, prefix="/inventaris", tags=["Inventaris"])

@app.on_event("startup")
async def startup():
    existing_collections = await db.list_collection_names()
    # Buat view 'barang_aktif' dari 'barang'
    if not "barang_aktif" in existing_collections:
        await db.command({
            "create": "barang_aktif",
            "viewOn": "barang",
            "pipeline": [
                { "$match": { "tanggal_dihapus": { "$exists": False } } }
            ]
        })
    logger.info("View 'barang_aktif' berhasil dibuat saat startup.")

@app.get("/")
def read_root():
    return {"message": "Welcome to Main Service API"}