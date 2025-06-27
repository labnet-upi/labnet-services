from fastapi import APIRouter, HTTPException, Query, Request, Depends
from auth import get_current_user
from typing import List
from utils.database import db, convert_objectid
from bson import ObjectId
from services.tugas_besar import getKelompokTubes, getNilaiKelompokTubes

router = APIRouter(dependencies=[Depends(get_current_user)])

# -----------------------------
# Routes
# -----------------------------
@router.get("/penilaian/daftar-kelompok")
async def get_daftar_kelompok(angkatan: int = Query(...)):
    daftarKelompok = await getKelompokTubes({"angkatan": angkatan})
    return daftarKelompok


@router.get("/penilaian/nilai-kelompok")
async def get_nilai_kelompok(id_kelompok: str = Query(...)):
    doc = await getNilaiKelompokTubes(id_kelompok)
    return doc

@router.post("/penilaian/nilai-kelompok")
async def post_nilai_kelompok(request: Request):
    body = await request.json()
    body["id_kelompok"] = ObjectId(body["id_kelompok"])
    for index, nilai in enumerate(body['nilai']):
        body['nilai'][index]['aspek_penilaian_id'] = ObjectId(nilai['aspek_penilaian_id'])
    
    result = await db.nilai_kelompok.update_one(
        {"id_kelompok": body["id_kelompok"]},
        {"$set": body},
        upsert=True
    )
    
    if result.modified_count == 0 and result.upserted_id is None:
        raise HTTPException(status_code=400, detail="Gagal menyimpan nilai kelompok")
    
    # mengembalikan upserted_id jika ada
    response = {
        "id_kelompok": body["id_kelompok"],
        "upserted_id": result.upserted_id if result.upserted_id else None
    }
    return convert_objectid(response)

@router.get("/penilaian/nilai-perorangan")
async def get_nilai_perorangan(id_kelompok: str = Query(...)):
    # Ambil info kelompok & anggota
    doc_kelompok_tubes = await getKelompokTubes({"_id": ObjectId(id_kelompok)})
    if not doc_kelompok_tubes:
        raise HTTPException(status_code=404, detail="Kelompok tidak ditemukan")

    kelompok = doc_kelompok_tubes[0]
    anggota = kelompok.get("anggota", [])

    hasil = []

    for item in anggota:
        nilai = await db.nilai_perorangan.find_one({"nim": item["nim"]})
        item_result = convert_objectid(nilai) if nilai else None
        hasil.append(item_result)

    return hasil

@router.post("/penilaian/nilai-perorangan")
async def post_nilai_perorangan(request: Request):
    body = await request.json()
    
    if not isinstance(body, list):
        raise HTTPException(status_code=400, detail="Payload harus berupa array")

    upserted_ids = []

    for item in body:
        if 'nim' not in item or 'nilai' not in item:
            raise HTTPException(status_code=400, detail="Setiap item harus memiliki 'nim' dan 'nilai'")
        
        # Konversi ObjectId pada aspek_penilaian_id
        for index, nilai in enumerate(item['nilai']):
            item['nilai'][index]['aspek_penilaian_id'] = ObjectId(nilai['aspek_penilaian_id'])

        # Lakukan upsert
        result = await db.nilai_perorangan.update_one(
            {"nim": item["nim"]},
            {"$set": item},
            upsert=True
        )

        if result.modified_count == 0 and result.upserted_id is None:
            raise HTTPException(status_code=400, detail=f"Gagal menyimpan nilai untuk NIM {item['nim']}")

        upserted_ids.append(result.upserted_id if result.upserted_id else item["nim"])

    return convert_objectid(upserted_ids)
