from fastapi import APIRouter, Query, Request, Depends
from auth import get_current_user
from bson import ObjectId
from services.tugas_besar import getAspekPenilaianKelompok, getAspekPenilaianPerorangan

router = APIRouter(dependencies=[Depends(get_current_user)])

async def upsert_aspek_penilaian(
    body: list,
    collection_name: str,
    get_result_function: callable
):
    if len(body) == 0:
        return []

    upserted_ids = []
    processed_ids = []
    tahun = body[0]["tahun"]
    collection = db[collection_name]

    async def update_or_upsert(document_id, update_data):
        filter_query = {"_id": ObjectId(document_id)} if document_id else update_data
        result = await collection.update_one(
            filter_query,
            {"$set": update_data},
            upsert=True
        )

        if result.upserted_id:
            new_id = str(result.upserted_id)
            upserted_ids.append(new_id)
            processed_ids.append(ObjectId(new_id))
            return new_id
        else:
            processed_ids.append(ObjectId(document_id))
            return document_id

    for item in body:
        parent_id = item.get("id")
        parent_data = {
            "kriteria": item["kriteria"],
            "tahun": tahun,
            "isParent": True
        }

        parent_id = await update_or_upsert(parent_id, parent_data)
        if parent_id is None:
            continue

        for child in item.get("children", []):
            await update_or_upsert(child.get("id"), {
                "kriteria": child["kriteria"],
                "bobot": child["bobot"],
                "tahun": tahun,
                "isParent": False,
                "parentId": ObjectId(parent_id)
            })

    # Hapus parent yang tidak diproses dan anak-anaknya
    unprocessed_parents = await collection.find({
        "tahun": tahun,
        "isParent": True,
        "_id": {"$nin": processed_ids}
    }).to_list(None)

    parent_ids_to_delete = [doc["_id"] for doc in unprocessed_parents]

    await collection.delete_many({
        "$or": [
            {"_id": {"$in": parent_ids_to_delete}},
            {"parentId": {"$in": parent_ids_to_delete}}
        ]
    })

    # Hapus child yang tidak diproses
    await collection.delete_many({
        "tahun": tahun,
        "isParent": False,
        "_id": {"$nin": processed_ids}
    })

    return await get_result_function([tahun])

# -----------------------------
# Routes
# -----------------------------
@router.get("/penilaian/aspek-penilaian-kelompok")
async def get_aspek_penilaian_kelompok(tahun: int = Query(...)):
    doc = await getAspekPenilaianKelompok([tahun])
    return doc

@router.post("/penilaian/aspek-penilaian-kelompok")
async def post_aspek_penilaian_kelompok(request: Request):
    body = await request.json()
    return await upsert_aspek_penilaian(
        body=body,
        collection_name="aspek_penilaian_kelompok",
        get_result_function=getAspekPenilaianKelompok
    )

@router.get("/penilaian/aspek-penilaian-perorangan")
async def get_aspek_penilaian_perorangan(tahun: int = Query(...)):
    doc = await getAspekPenilaianPerorangan([tahun])
    return doc

@router.post("/penilaian/aspek-penilaian-perorangan")
async def post_aspek_penilaian_perorangan(request: Request):
    body = await request.json()
    return await upsert_aspek_penilaian(
        body=body,
        collection_name="aspek_penilaian_perorangan",
        get_result_function=getAspekPenilaianPerorangan
    )
