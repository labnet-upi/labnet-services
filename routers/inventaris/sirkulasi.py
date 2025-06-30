from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from core.auth import get_current_user
from utils.database import db, convert_objectid
from bson import ObjectId
from services.inventaris import *

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/")
async def get_form_sirkulasi(id_formulir: Optional[str] = None):
    pipeline = getPipeLineFormSirkulasi(id_formulir)
    cursor = db.formulir_sirkulasi_barang.aggregate(pipeline)
    if id_formulir:
        result = await cursor.to_list(length=1)
        result = result[0]
    else:
        result = await cursor.to_list(length=None)
    return convert_objectid(result)

@router.post("/")
async def post_sirkulasi(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    formulir, formulir_id = await simpanFormulirSirkulasiBarang(body["penanggung_jawab"], ObjectId(current_user["_id"]))
    barang_raw = body["barang"]
    barang_dicatat = await simpanBarangSirkulasi(barang_raw, formulir, formulir_id)
    result = await perbaruiJumlahTerkiniBarang(formulir, barang_raw)

    if formulir["status_sirkulasi"] == "Pengembalian":
        await kurangiJumlahBelumDikembalikanBarangSirkulasi(barang_dicatat)
        await perbaruStatusPengembalianBarang(str(formulir["id_formulir_sebelumnya"]))
        
    return {
        "message": "Peminjaman berhasil dicatat",
        "formulir_id": convert_objectid(formulir_id),
        "jumlah_barang_dicatat": len(barang_dicatat),
        "jumlah_barang_diupdate": result.modified_count
    }
