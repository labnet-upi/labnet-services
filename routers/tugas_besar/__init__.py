from . import penilaian, rekap, aspek
from fastapi import APIRouter

router = APIRouter()

router.include_router(penilaian.router, prefix="/penilaian", tags=["penilaian"])
router.include_router(rekap.router, prefix="/rekap", tags=["rekap"])
router.include_router(aspek.router, prefix="/aspek", tags=["aspek"])