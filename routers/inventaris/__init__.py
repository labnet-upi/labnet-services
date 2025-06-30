from . import barang, sirkulasi
from fastapi import APIRouter

router = APIRouter()

router.include_router(barang.router, prefix="/barang", tags=["Barang"])
router.include_router(sirkulasi.router, prefix="/sirkulasi", tags=["Sirkulasi"])