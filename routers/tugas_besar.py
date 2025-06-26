from fastapi import APIRouter, HTTPException, Query, Request, Depends
from auth import get_current_user
from pydantic import BaseModel, Field
from typing import List
from database import db, convert_objectid
from bson import ObjectId
from utils import generate_csv_response, generate_excel_response

router = APIRouter(dependencies=[Depends(get_current_user)])

# -----------------------------
# Routes
# -----------------------------
@router.get("/penilaian/daftar-kelompok")
async def get_daftar_kelompok(angkatan: int = Query(...)):
    cursor = db.kelompok_tubes.aggregate([
        {"$match": {"angkatan": angkatan}},
        {
            "$lookup": {
                "from": "users",
                "localField": "nim_anggota",
                "foreignField": "nim",
                "as": "anggota"
            }
        },
        {
            "$project": {
                "nomor": 1,
                "kelas": 1,
                "angkatan": 1,
                "laporan": 1,
                "anggota.nama": 1,
                "anggota.nim": 1,
            }
        }
    ])

    doc = await cursor.to_list(length=None)
    return convert_objectid(doc)

@router.get("/penilaian/aspek-penilaian-kelompok")
async def get_aspek_penilaian_kelompok(tahun: int = Query(...)):
    cursor = db.aspek_penilaian_kelompok.aggregate([
        {"$match": {"isParent": True, "tahun": tahun}},
        {"$lookup": {
            "from": "aspek_penilaian_kelompok",             # collection yang sama
            "localField": "_id",            # parent _id
            "foreignField": "parentId",    # child parentId
            "as": "children"
        }}
    ])

    doc = await cursor.to_list(length=None)
    return convert_objectid(doc)

@router.get("/penilaian/nilai-kelompok")
async def get_nilai_kelompok(id_kelompok: str = Query(...)):
    doc = await db.nilai_kelompok.find_one({"id_kelompok": ObjectId(id_kelompok)})
    if not doc:
        return []
    
    return convert_objectid(doc)

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

@router.get("/penilaian/aspek-penilaian-perorangan")
async def get_aspek_penilaian_perorangan(tahun: int = Query(...)):
    cursor = db.aspek_penilaian_perorangan.aggregate([
        {"$match": {"isParent": True, "tahun": tahun}},
        {"$lookup": {
            "from": "aspek_penilaian_perorangan",             # collection yang sama
            "localField": "_id",            # parent _id
            "foreignField": "parentId",    # child parentId
            "as": "children"
        }}
    ])

    doc = await cursor.to_list(length=None)
    return convert_objectid(doc)

@router.get("/penilaian/nilai-perorangan")
async def get_nilai_perorangan(id_kelompok: str = Query(...)):
    # Ambil info kelompok & anggota
    cursor_kelompok_tubes = db.kelompok_tubes.aggregate([
        {"$match": {"_id": ObjectId(id_kelompok)}},
        {
            "$lookup": {
                "from": "users",
                "localField": "nim_anggota",
                "foreignField": "nim",
                "as": "anggota"
            }
        },
        {
            "$project": {
                "nomor": 1,
                "kelas": 1,
                "angkatan": 1,
                "laporan": 1,
                "anggota.nama": 1,
                "anggota.nim": 1,
            }
        }
    ])

    doc_kelompok_tubes = await cursor_kelompok_tubes.to_list(length=None)
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

@router.get("/rekap/nilai-kelompok")
async def get_rekap_nilai_kelompok(
    tahun: int = Query(...), 
    kelas: str = Query(...),
    format: str = Query("json")
):
    query = {"tahun": tahun, "kelas": kelas}
    cursor = db.nilai_kelompok.find(query)
    data = [convert_objectid(doc) async for doc in cursor]

    if format == "csv":
        return generate_csv_response(data, filename="rekap_nilai.csv")
    elif format == "excel":
        return generate_excel_response(data, filename="rekap_nilai.xlsx", sheet_name="Nilai")
    else:
        return data

@router.get("/rekap/nilai-perorangan")
async def get_rekap_nilai_perorangan(
    tahun: int = Query(...), 
    kelas: str = Query(...),
    format: str = Query("json")
):
    query = {"tahun": tahun, "kelas": kelas}
    cursor = db.nilai_perorangan.find(query)
    data = [convert_objectid(doc) async for doc in cursor]

    if format == "csv":
        return generate_csv_response(data, filename="rekap_nilai.csv")
    elif format == "excel":
        return generate_excel_response(data, filename="rekap_nilai.xlsx", sheet_name="Nilai")
    else:
        return data