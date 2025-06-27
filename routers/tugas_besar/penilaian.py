from fastapi import APIRouter, HTTPException, Query, Request, Depends
from core.auth import get_current_user
from utils.database import db, convert_objectid
from bson import ObjectId
from services.tugas_besar import getKelompokTubes, getNilaiKelompokTubes, getNilaiPerorangan

router = APIRouter(dependencies=[Depends(get_current_user)])

# -----------------------------
# Routes
# -----------------------------
@router.get("/daftar-kelompok")
async def get_daftar_kelompok(tahun: int = Query(...)):
    daftarKelompok = await getKelompokTubes({"tahun": tahun})
    return daftarKelompok


@router.get("/nilai-kelompok")
async def get_nilai_kelompok(
    id_kelompok: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    doc = await getNilaiKelompokTubes(id_kelompok, current_user["_id"])
    return convert_objectid(doc)

@router.post("/nilai-kelompok")
async def post_nilai_kelompok(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    id_kelompok = ObjectId(body["id_kelompok"])
    body["id_kelompok"] = ObjectId(body["id_kelompok"])
    object_id_penilai = ObjectId(current_user["_id"])
    for index, nilai in enumerate(body['nilai']):
        body['nilai'][index]['aspek_penilaian_id'] = ObjectId(nilai['aspek_penilaian_id'])
    
    await db.nilai_kelompok.update_one(
        {"id_kelompok": body["id_kelompok"], "id_penilai": object_id_penilai},
        {"$set": body},
        upsert=True
    )

    doc = await getNilaiKelompokTubes(id_kelompok, current_user["_id"])
    return convert_objectid(doc)

@router.get("/nilai-perorangan")
async def get_nilai_perorangan(
    id_kelompok: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    hasil = await getNilaiPerorangan(id_kelompok, current_user["_id"])
    return hasil

@router.post("/nilai-perorangan")
async def post_nilai_perorangan(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    
    if not isinstance(body, list):
        raise HTTPException(status_code=400, detail="Payload harus berupa array")
    object_id_penilai = ObjectId(current_user["_id"])
    id_kelompok = body[0]["id_kelompok"]
    object_id_kelompok = ObjectId(id_kelompok)
    for item in body:
        if 'id_mahasiswa' not in item or 'nilai' not in item:
            raise HTTPException(status_code=400, detail="Setiap item harus memiliki 'id_mahasiswa' dan 'nilai'")
        
        item['id_penilai'] = object_id_penilai
        item["id_kelompok"] = object_id_kelompok
        item["id_mahasiswa"] = ObjectId(item["id_mahasiswa"])
        
        # Konversi ObjectId pada aspek_penilaian_id
        for index, nilai in enumerate(item['nilai']):
            item['nilai'][index]['aspek_penilaian_id'] = ObjectId(nilai['aspek_penilaian_id'])

        # Lakukan upsert
        result = await db.nilai_perorangan.update_one(
            {"id_mahasiswa": item["id_mahasiswa"], "id_penilai": object_id_penilai},
            {"$set": item},
            upsert=True
        )
    hasil = await getNilaiPerorangan(id_kelompok, current_user["_id"])
    return hasil
