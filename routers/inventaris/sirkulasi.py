from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from core.auth import get_current_user
from utils.database import db, convert_objectid
from bson import ObjectId
from services.inventaris import *
from utils.generate_file_response import generate_excel_response

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
        result = await getListSirkulasi()
    return convert_objectid(result)

@router.get("/laporan")
async def get_laporan():
    raw_data = await getListSirkulasi()
    result = []
    for formulir in raw_data:
        result_barang = ";".join(f"{barang_sirkulasi['barang']['kode']}:{barang_sirkulasi['jumlah_dicatat']}" for barang_sirkulasi in formulir["data_barang_sirkulasi"])
        temp_result = {
            "nama": formulir["nama"],
            "notel": formulir["notel"],
            "status": formulir["status_sirkulasi"],
            "barang": result_barang,
            "pencatat": formulir["pencatat"]["nama"],
            "notel_pencatat": formulir["pencatat"]["nama"],
            "tanggal_pencatatan": formulir["tanggal_pencatatan"],
        }
        result.append(temp_result)
    today_str = datetime.today().strftime('%Y%m%d')
    filename = f"laporan_sirkulasi_{today_str}.xlsx"
    return generate_excel_response(result, filename)

@router.post("/")
async def post_sirkulasi(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    formulir, formulir_id = await upsertFormulirSirkulasiBarang(body["penanggung_jawab"], ObjectId(current_user["_id"]), True)
    barang_raw = body["barang"]
    barang_dicatat = await upsertBarangSirkulasi(barang_raw, formulir, formulir_id)
    result = await perbaruiJumlahTerkiniBarang(formulir, barang_raw, formulir["status_sirkulasi"] != "peminjaman", "id")

    if formulir["status_sirkulasi"] == "pengembalian":
        await perbaruiJumlahBelumDikembalikanBarangSirkulasi(barang_dicatat, False)
        await perbaruStatusPengembalianBarang(str(formulir["id_formulir_sebelumnya"]))
        
    return {
        "message": "Peminjaman berhasil dicatat",
        "formulir_id": convert_objectid(formulir_id),
        "jumlah_barang_dicatat": len(barang_dicatat),
        "jumlah_barang_diupdate": result.modified_count
    }

@router.patch("/")
async def patch_sirkulasi(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    #periksa apakah peminjaman
    formulir_request = body["penanggung_jawab"]
    if formulir_request["status_sirkulasi"] != "peminjaman":
        return { "message" : "belum tersedia untuk pengembalian"}
    
    #perbarui formulir peminjaman
    formulir, formulir_id = await upsertFormulirSirkulasiBarang(formulir_request, ObjectId(current_user["_id"]), False)
    #perbarui jumlah terkini barang
    result_sinkorinasi = await perbaruiDanSinkronisasiBarang(formulir, body)
    #perbarui barang sirkulasi
    barang_raw = body["barang"]
    barang_dicatat = await upsertBarangSirkulasi(barang_raw, formulir, formulir_id)
            
    return {
        "message": "Peminjaman berhasil diubah",
        "formulir_id": convert_objectid(formulir_id),
        "jumlah_barang_dicatat": len(barang_dicatat),
        "update_bingung_hehe": convert_objectid(result_sinkorinasi)
    }

@router.delete("/")
async def delete_sirkulasi(id_formulir: str):
    formulir = await getFormulirSirkulasi(id_formulir)
    result={}
    if formulir["status_sirkulasi"] == "peminjaman":
        result["jumlah_barang_diganti"] = await kembalikanJumlahTerkiniBarang(formulir)
        result["jumlah_barang_sirkulasi_dihapus"] = await hapusBarangSirkulasi(formulir["_id"])
    else:
        result["jumlah_formulir_diganti"] = await perbaruiStatusDikembalikanFormulirSirkulasi(formulir["id_formulir_sebelumnya"])
        result["jumlah_barang_sirkulasi_diganti"] = await kembalikanJumlahBarangSirkulasi(formulir["_id"])
        result["jumlah_barang_diganti"] = await kembalikanJumlahTerkiniBarang(formulir)

    # hapus formulir
    result["jumlah_formulir_sirkulasi_dihapus"] = await hapusFormulirSirkulasi(formulir["_id"])
    return []
