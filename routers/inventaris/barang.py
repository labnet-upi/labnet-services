from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from core.auth import get_current_user
from utils.database import db, convert_objectid, flatten_with_relations, convert_to_objectid
from bson import ObjectId
from datetime import datetime, timezone
from services.inventaris import get_barang_pipeline, sync_barang_hirarki

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/")
async def get_barang(status: Literal["semua", "dipinjam", "tidak_dipinjam"] = "semua"):
    cursor = db.barang_aktif.aggregate(get_barang_pipeline(status))
    result = await cursor.to_list(length=None)
    return convert_objectid(result)

@router.get("/saran-isi")
async def get_saran_isi():
    cursor = db.barang_aktif.aggregate([
        { "$sort": { "nama": -1 } },
        {
            "$group": {
            "_id": "$nama",
            "doc": { "$first": "$$ROOT" }
            }
        },
        {
            "$replaceRoot": { "newRoot": "$doc" }
        }
    ])
    result = await cursor.to_list(length=None)
    return convert_objectid(result)

@router.post("/")
async def post_barang(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    flatten_data, relation_data = flatten_with_relations(body)
    flatten_data = convert_to_objectid(flatten_data)
    relation_data = convert_to_objectid(relation_data)
    object_id_user = ObjectId(current_user["_id"])
    tanggal_pengisian = datetime.now(timezone.utc)

    if flatten_data:
        for data in flatten_data:
            data["id_pengisi"] = object_id_user
            data["tanggal_pengisian"] = tanggal_pengisian
            data["jumlah_terkini"] = data["jumlah"]
        await db.barang.insert_many(flatten_data)
    if relation_data:
        await db.barang_hirarki.insert_many(relation_data)
    
    return {
        "inserted_barang": convert_objectid(flatten_data),
        "inserted_relasi": convert_objectid(relation_data)
    }

@router.put("/")
async def put_barang(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    object_id_user = ObjectId(current_user["_id"])
    tanggal_diubah = datetime.now(timezone.utc)
    object_barang_id = ObjectId(body["id"])

    data_lama = await db.barang.find_one({"_id": object_barang_id})
    if not data_lama:
        return {"error": "Data tidak ditemukan."}
    
    jumlah_pada_data_lama = data_lama.get("jumlah", 0)
    jumlah_pada_data_baru = body.get("jumlah", 0)
    selisih = jumlah_pada_data_baru - jumlah_pada_data_lama
    jumlah_terkini = data_lama["jumlah_terkini"] + selisih

    result_update_barang = await db.barang.update_one(
        {"_id": object_barang_id},
        {
            "$set": {
                "nama": body["nama"],
                "kode": body["kode"],
                "kondisi": body["kondisi"],
                "satuan": body["satuan"],
                "jumlah": body["jumlah"],
                "id_pengubah": object_id_user,
                "tanggal_diubah": tanggal_diubah,
                "jumlah_terkini": jumlah_terkini
            }
        }
    )

    result_update_barang_hirarki = await sync_barang_hirarki(object_barang_id, body["children"])
    return {
        "jumlah_update_barang_lama": result_update_barang.modified_count,
        "barang_hirarki":  result_update_barang_hirarki
    }

@router.delete("/")
async def delete_barang(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    body = await request.json()
    list_barang_id = [ObjectId(id_barang) for id_barang in body["list_id_barang"]]
    tanggal_dihapus = datetime.now(timezone.utc)
    result = await db.barang.update_many(
        { "_id": { "$in": list_barang_id } },
        {
            "$set": {
                "id_penghapus": current_user["_id"],
                "tanggal_dihapus": tanggal_dihapus
            }
        }
    )
    return {
        "modified_count": result.modified_count,
        "matched_count": result.matched_count
    }
