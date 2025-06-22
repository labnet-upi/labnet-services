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
async def get_daftar_kelompok():
    cursor = db.kelompok.find()
    result = [
        convert_objectid(doc) async for doc in cursor
    ]
    return result

@router.get("/penilaian/aspek-penilaian-kelompok")
async def get_aspek_penilaian_kelompok(tahun: int = Query(...)):
    doc = await db.aspek_penilaian_kelompok.aggregate(
        {"$match": {"isParent": True, "tahun": tahun}},
        {"$lookup": {
            "from": "kriteria",             # collection yang sama
            "localField": "_id",            # parent _id
            "foreignField": "parent_id",    # child parent_id
            "as": "children"
        }}
    )
    
    return convert_objectid(doc)

@router.get("/penilaian/nilai-kelompok")
async def get_nilai_kelompok(id_kelompok: str = Query(...)):
    doc = await db.nilai_kelompok.find_one({"id_kelompok": id_kelompok})
    if not doc:
        return {"message": "Nilai kelompok tidak ditemukan"}
    
    return convert_objectid(doc)

@router.post("/penilaian/nilai-kelompok")
async def post_nilai_kelompok(request: Request):
    body = await request.json()
    result = await db.nilai_kelompok.insert_many(body)
    inserted_ids = [str(_id) for _id in result.inserted_ids]
    return {
        "inserted_ids": convert_objectid(inserted_ids)
    }

@router.get("/penilaian/aspek-penilaian-perorangan")
async def get_aspek_penilaian_kelompok(tahun: int = Query(...)):
    doc = await db.aspek_penilaian_perorangan.aggregate(
        {"$match": {"isParent": True, "tahun": tahun}},
        {"$lookup": {
            "from": "kriteria",             # collection yang sama
            "localField": "_id",            # parent _id
            "foreignField": "parent_id",    # child parent_id
            "as": "children"
        }}
    )
    
    return convert_objectid(doc)

@router.get("/penilaian/nilai-perorangan")
async def get_nilai_perorangan(id_kelompok: str = Query(...)):
    # Ambil nilai mahasiswa per individu dalam kelompok tertentu
    cursor = db.nilai_perorangan.find({"id_kelompok": id_kelompok})
    result = [convert_objectid(doc) async for doc in cursor]
    return result

@router.post("/penilaian/nilai-perorangan")
async def post_nilai_perorangan(request: Request):
    body = await request.json()
    result = await db.nilai_perorangan.insert_many(body)
    inserted_ids = [str(_id) for _id in result.inserted_ids]
    return {
        "inserted_ids": convert_objectid(inserted_ids)
    }

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