from fastapi import APIRouter, HTTPException, Query, Request, Depends
from auth import get_current_user
from pydantic import BaseModel, Field
from typing import List
from database import db, convert_objectid
from bson import ObjectId
from utils import generate_csv_response, generate_excel_response

router = APIRouter(dependencies=[Depends(get_current_user)])

async def getKelompokTubes(matchCondition: dict):
    cursor = db.kelompok_tubes.aggregate([
        {"$match": matchCondition},
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

async def getNilaiKelompokTubes(id_kelompok: str):
    doc = await db.nilai_kelompok.find_one({"id_kelompok": ObjectId(id_kelompok)})
    if not doc:
        return []
    
    return doc

async def getAspekPenilaianKelompok(tahun: List[int]):
    cursor = db.aspek_penilaian_kelompok.aggregate([
        {"$match": {
            "isParent": True,
            "tahun": { "$in" : tahun }
        }},
        {"$lookup": {
            "from": "aspek_penilaian_kelompok",             # collection yang sama
            "localField": "_id",            # parent _id
            "foreignField": "parentId",    # child parentId
            "as": "children"
        }}
    ])

    doc = await cursor.to_list(length=None)
    return convert_objectid(doc)

async def getAspekPenilaianPerorangan(tahun: int):
    cursor = db.aspek_penilaian_perorangan.aggregate([
        {"$match": {
            "isParent": True,
            "tahun": { "$in" : tahun }
        }},
        {"$lookup": {
            "from": "aspek_penilaian_perorangan",             # collection yang sama
            "localField": "_id",            # parent _id
            "foreignField": "parentId",    # child parentId
            "as": "children"
        }}
    ])

    doc = await cursor.to_list(length=None)
    return convert_objectid(doc)

def extract_children_only(data, key_children="children"):
    result = []

    def recurse(node, has_parent=False):
        if has_parent:
            flat_node = {k: v for k, v in node.items() if k != key_children}
            result.append(flat_node)
        for child in node.get(key_children, []):
            recurse(child, has_parent=True)

    if isinstance(data, list):
        for item in data:
            recurse(item, has_parent=False)
    elif isinstance(data, dict):
        recurse(data, has_parent=False)
    else:
        raise TypeError("Input harus berupa dict atau list of dicts")

    return result

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
@router.get("/penilaian/daftar-kelompok")
async def get_daftar_kelompok(angkatan: int = Query(...)):
    daftarKelompok = await getKelompokTubes({"angkatan": angkatan})
    return daftarKelompok

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

async def getNilaiPerKelompok(tahun, kelas):
# dapatkan data kelompok tubes dan aspek penilaian kelompok
    kelompok_tubes_condition = {
        "angkatan": { "$in" : tahun },
        "kelas": { "$in" : kelas }
    }
    doc_kelompok_tubes = await getKelompokTubes(kelompok_tubes_condition)
    doc_aspek_penilaian_kelompok = await getAspekPenilaianKelompok(tahun)
    doc_aspek_penilaian_kelompok = extract_children_only(doc_aspek_penilaian_kelompok)

    for kelompok in doc_kelompok_tubes:
        # ambil nilai kelompok
        doc_nilai_kelompok = await db.nilai_kelompok.find_one({"id_kelompok": ObjectId(kelompok["id"])})
        
        nilaiAkhir = 0
        if doc_nilai_kelompok:
            item_nilai_kelompok = convert_objectid(doc_nilai_kelompok.get("nilai", []))
            for item in item_nilai_kelompok:
                # cari bobot dari aspek penilaian
                bobot = next((ap["bobot"] for ap in doc_aspek_penilaian_kelompok if ap["id"] == item["aspek_penilaian_id"]), 0)
                # jumlahkan nilai akhir
                nilaiAkhir += (item["nilai"] * bobot / 100)
        
        kelompok["nilaiAkhir"] = nilaiAkhir
    return doc_kelompok_tubes

@router.get("/rekap/nilai-kelompok")
async def get_rekap_nilai_kelompok(
    tahun: List[int] = Query(...), 
    kelas: List[str] = Query(...),
    format: str = Query("json")
):
    doc_kelompok_tubes = await getNilaiPerKelompok(tahun, kelas)
    doc_kelompok_tubes = sorted(doc_kelompok_tubes, key=lambda x: x["nilaiAkhir"], reverse=True)

    if format == "csv":
        return generate_csv_response(doc_kelompok_tubes, filename="rekap_nilai.csv")
    elif format == "excel":
        return generate_excel_response(doc_kelompok_tubes, filename="rekap_nilai.xlsx", sheet_name="Nilai")
    else:
        return doc_kelompok_tubes

@router.get("/rekap/nilai-perorangan")
async def get_rekap_nilai_perorangan(
    tahun: List[int] = Query(...), 
    kelas: List[str] = Query(...),
    format: str = Query("json")
):
    doc_kelompok_tubes = await getNilaiPerKelompok(tahun, kelas)
    doc_aspek_penilaian_perorangan = await getAspekPenilaianPerorangan(tahun)
    doc_aspek_penilaian_perorangan = extract_children_only(doc_aspek_penilaian_perorangan)

    doc_rekap_nilai_perorangan = []
    for kelompok in doc_kelompok_tubes:
        anggota = kelompok.get("anggota", [])
        for anggota_item in anggota:
            # ambil nilai perorangan
            doc_nilai_perorangan = await db.nilai_perorangan.find_one({"nim": anggota_item["nim"]})
            nilai_kelompok = kelompok.get("nilaiAkhir", 0)
            nilai_perorangan = 0
            if not doc_nilai_perorangan:
                nilaiAkhir = (nilai_perorangan + nilai_kelompok) / 2
                doc_rekap_nilai_perorangan.append({
                    "nama": anggota_item["nama"],
                    "nim": anggota_item["nim"],
                    "kelas": kelompok["kelas"],
                    "angkatan": kelompok["angkatan"],
                    "nomor": kelompok["nomor"],
                    "nilaiPerorangan": 0,
                    "nilaiKelompok": nilai_kelompok,
                    "nilaiAkhir": nilaiAkhir
                })
                continue
            
            # konversi nilai perorangan
            data_nilai_perorangan = convert_objectid(doc_nilai_perorangan.get("nilai", []))
            for item in data_nilai_perorangan:
                # cari bobot dari aspek penilaian
                bobot = next((ap["bobot"] for ap in doc_aspek_penilaian_perorangan if ap["id"] == item["aspek_penilaian_id"]), 0)
                # jumlahkan nilai akhir
                nilai_perorangan += (item["nilai"] * bobot / 100)

            nilaiAkhir = (nilai_perorangan + nilai_kelompok) / 2
            doc_rekap_nilai_perorangan.append({
                "nama": anggota_item["nama"],
                "nim": anggota_item["nim"],
                "kelas": kelompok["kelas"],
                "angkatan": kelompok["angkatan"],
                "nomor": kelompok["nomor"],
                "nilaiPerorangan": nilai_perorangan,
                "nilaiKelompok": nilai_kelompok,
                "nilaiAkhir": nilaiAkhir
            })
    doc_rekap_nilai_perorangan = sorted(doc_rekap_nilai_perorangan, key=lambda x: x["nilaiAkhir"], reverse=True)

    if format == "csv":
        return generate_csv_response(doc_rekap_nilai_perorangan, filename="rekap_nilai.csv")
    elif format == "excel":
        return generate_excel_response(doc_rekap_nilai_perorangan, filename="rekap_nilai.xlsx", sheet_name="Nilai")
    else:
        return doc_rekap_nilai_perorangan