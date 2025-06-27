from typing import List
from utils.database import db, convert_objectid
from bson import ObjectId

async def getKelompokTubes(matchCondition: dict):
    cursor = db.kelompok_tubes.aggregate([
        {"$match": matchCondition},
        {
            "$lookup": {
                "from": "users",
                "localField": "id_anggota",
                "foreignField": "_id",
                "as": "anggota"
            }
        },
        {
            "$project": {
                "nomor": 1,
                "kelas": 1,
                "tahun": 1,
                "laporan": 1,
                "anggota._id": 1,
                "anggota.nama": 1,
                "anggota.nim": 1,
            }
        }
    ])

    doc = await cursor.to_list(length=None)
    return convert_objectid(doc)

async def getNilaiKelompokTubes(id_kelompok: str, id_penilai):
    doc = await db.nilai_kelompok.find_one({"id_kelompok": ObjectId(id_kelompok), "id_penilai": ObjectId(id_penilai)})
    if not doc:
        return []
    
    return doc

async def getNilaiPerorangan(id_kelompok, id_penilai):
    doc_kelompok_tubes = await getKelompokTubes({"_id": ObjectId(id_kelompok)})
    if not doc_kelompok_tubes:
        return []

    kelompok = doc_kelompok_tubes[0]
    anggota = kelompok.get("anggota", [])
    hasil = []
    for item in anggota:
        # hasil.append(item)
        nilai = await db.nilai_perorangan.find_one({"id_mahasiswa": ObjectId(item["id"]), "id_penilai": ObjectId(id_penilai)})
        item_result = convert_objectid(nilai) if nilai else None
        hasil.append(item_result)

    return hasil

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

async def getNilaiPerKelompok(tahun, kelas):
# dapatkan data kelompok tubes dan aspek penilaian kelompok
    kelompok_tubes_condition = {
        "tahun": { "$in" : tahun },
        "kelas": { "$in" : kelas }
    }
    doc_kelompok_tubes = await getKelompokTubes(kelompok_tubes_condition)
    doc_aspek_penilaian_kelompok = await getAspekPenilaianKelompok(tahun)
    doc_aspek_penilaian_kelompok = extract_children_only(doc_aspek_penilaian_kelompok)

    for kelompok in doc_kelompok_tubes:
        # ambil nilai kelompok oleh semua panelis
        doc_nilai_kelompok = await db.nilai_kelompok.find({"id_kelompok": ObjectId(kelompok["id"])}).to_list(length=None)

        # hitung per panelis
        nilai_akhir = 0
        jumlah_panelis = 0
        for nilai_panelis in doc_nilai_kelompok:
            jumlah_panelis += 1
            
            nilai_akhir_panelis = 0
            item_nilai = convert_objectid(nilai_panelis.get("nilai", []))
            for item in item_nilai:
                # cari bobot dari aspek penilaian
                bobot = next((ap["bobot"] for ap in doc_aspek_penilaian_kelompok if ap["id"] == item["aspek_penilaian_id"]), 0)
                # jumlahkan nilai akhir panelis
                nilai_akhir_panelis += (item["nilai"] * bobot / 100)
            nilai_akhir += nilai_akhir_panelis
            del nilai_panelis["nilai"]

        # hiung nilai akhir dari semua panelis
        kelompok["nilaiAkhir"] = (nilai_akhir / jumlah_panelis) if jumlah_panelis > 0 else 0
    return doc_kelompok_tubes

