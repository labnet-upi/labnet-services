from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from core.auth import get_current_user
from utils.database import db, convert_objectid
from bson import ObjectId
from services.inventaris import *

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/")
async def get_form_sirkulasi(status_sirkulasi: Optional[str] = "semua", id_formulir: Optional[str] = None):
    if id_formulir:
        informasi_sirkulasi = await getFormulirSirkulasi(id_formulir)
        pilihan_barang = await getDataBarangSirkulasi(id_formulir, status_sirkulasi == "peminjaman")
        result = {
            "informasi_sirkulasi": informasi_sirkulasi,
            "pilihan_barang": pilihan_barang
        }
    else:
        pipeline = getPipeLineFormSirkulasi()
        cursor = db.formulir_sirkulasi_barang.aggregate(pipeline)
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
