from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from core.auth import get_current_user
from utils.database import db, convert_objectid, flatten_with_relations, convert_to_objectid, filter_top_level_nodes
from bson import ObjectId
from datetime import datetime, timezone
from services.inventaris import get_barang_pipeline

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/")
async def get_barang(status: Literal["semua", "dipinjam", "tidak_dipinjam"] = "semua"):
    cursor = db.barang.aggregate(get_barang_pipeline(status))
    result = await cursor.to_list(length=None)
    return convert_objectid(result)

@router.get("/saran-isi")
async def get_saran_isi():
    cursor = db.barang.aggregate([
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
async def put_barang(request: Request):
    body = await request.json()
    return []

@router.delete("/")
async def put_barang(request: Request):
    body = await request.json()
    return [] 
