from typing import Optional
from typing import Literal
from bson import ObjectId
from pymongo import UpdateOne
from datetime import datetime, timezone
from utils.database import db
def get_barang_pipeline(
    status: Literal["semua", "dipinjam", "tidak_dipinjam"] = "semua"
):
    pipeline = [
        {
            "$lookup": {
                "from": "barang_hirarki",
                "localField": "_id",
                "foreignField": "childId",
                "as": "isChild"
            }
        },
        {
            "$match": {
                "isChild": { "$eq": [] }
            }
        },
        {
            "$lookup": {
                "from": "barang_hirarki",
                "localField": "_id",
                "foreignField": "parentId",
                "as": "relations"
            }
        },
        {
            "$lookup": {
                "from": "barang",
                "let": { "children_ids": "$relations.childId" },
                "pipeline": [
                    { "$match": { "$expr": { "$in": ["$_id", "$$children_ids"] } } }
                ],
                "as": "children"
            }
        },
        {
            "$project": {
                "_id": 1,
                "nama": 1,
                "kode": 1,
                "kondisi": 1,
                "satuan": 1,
                "jumlah": 1,
                "jumlah_terkini": 1,
                "children": 1
            }
        }
    ]

    if(status == "tidak_dipinjam"):
        pipeline.insert(0, { "$match": { "jumlah_terkini": { "$gt": 0 } } })
    elif(status == "dipinjam"):
        pipeline.insert(0, { "$match": { "$expr" : { "$lt" : ["$jumlah_terkini", "$jumlah"] }}})

    return pipeline

def getPipeLineFormSirkulasi(id_formulir: Optional[str]):
    pipeline = [
        {
            "$lookup": {
            "from": "barang_sirkulasi",
            "let": { "formulirId": "$_id" },
            "pipeline": [
                {
                "$match": {
                    "$expr": {
                        "$eq": [
                            { "$toObjectId": "$id_formulir" },
                            "$$formulirId"
                        ]
                    }
                }
                },
                {
                "$lookup": {
                    "from": "barang",
                    "localField": "id_barang",
                    "foreignField": "_id",
                    "as": "barang"
                }
                },
                {
                "$unwind": {
                    "path": "$barang",
                    "preserveNullAndEmptyArrays": True
                }
                }
            ],
            "as": "data_barang_sirkulasi"
            }
        },
    ]

    if id_formulir:
        pipeline.insert(0, { "$match": { "_id": ObjectId(id_formulir) }})
    else:
        pipeline.extend([
            {
                "$lookup": {
                "from": "users",
                "localField": "id_pencatat",
                "foreignField": "_id",
                "as": "pencatat"
                }
            },
            {
                "$unwind": {
                "path": "$pencatat",
                "preserveNullAndEmptyArrays": True
                }
            },
            { "$sort": { "tanggal_pencatatan": -1 } }
        ])
    return pipeline

async def simpanFormulirSirkulasiBarang(data_penanggung_jawab, object_user_id):
    pj = data_penanggung_jawab
    tanggal_pencatatan = datetime.fromisoformat(pj["tanggal"]).isoformat()
    formulir = {
        "_id": ObjectId(pj["id"]),
        "nama": pj["nama"],
        "notel": pj["notel"],
        "keterangan": pj["keterangan"],
        "status_sirkulasi": pj["status_sirkulasi"],
        "id_pencatat": object_user_id,
        "tanggal_pencatatan": tanggal_pencatatan,
        **(
            {"sudah_dikembalikan_semua": False}
            if pj["status_sirkulasi"] == "Peminjaman"
            else {"id_formulir_sebelumnya": ObjectId(pj["id_formulir_sebelumnya"])}
        )
    }

    result = await db.formulir_sirkulasi_barang.insert_one(formulir)
    id_formulir = result.inserted_id
    return formulir, id_formulir

async def perbaruStatusPengembalianBarang(id_formulir):
    pipeline = getPipeLineFormSirkulasi(id_formulir)
    cursor = db.formulir_sirkulasi_barang.aggregate(pipeline)
    result = await cursor.to_list(length=1)
    result = result[0]
    print(result)

    i = 0
    data_barang_sirkulasi = result["data_barang_sirkulasi"]
    sudahDikembalikanSemua = all(
        barang_sirkulasi["jumlah_belum_dikembalikan"] == 0 for barang_sirkulasi in result["data_barang_sirkulasi"]
    )
    if sudahDikembalikanSemua:
        db.formulir_sirkulasi_barang.update_one(
            {"_id": ObjectId(id_formulir)},
            {
                "$set": { "sudah_dikembalikan_semua": True }
            }
        )
    return sudahDikembalikanSemua
    

async def simpanBarangSirkulasi(barang_raw, formulir, id_formulir):
    barang_dicatat = [
        {
            "id_barang": ObjectId(barang["id"]),
            "status_sirkulasi": formulir["status_sirkulasi"],
            "keterangan": barang.get("keterangan", ""),
            "jumlah_dicatat": barang.get("jumlah_dicatat", 0),
            "id_formulir": id_formulir,
            **(
                {"id_barang_sirkulasi_sebelumnya": ObjectId(barang["id_barang_sirkulasi_sebelumnya"])}
                if formulir["status_sirkulasi"] == "Pengembalian" and "id_barang_sirkulasi_sebelumnya" in barang
                else {"jumlah_belum_dikembalikan": barang.get("jumlah_dicatat", 0),}
            )
        }
        for barang in barang_raw
    ]

    await db.barang_sirkulasi.insert_many(barang_dicatat)
    return barang_dicatat

async def kurangiJumlahBelumDikembalikanBarangSirkulasi(barang_sirkulasi_terkini):
    operations = []

    for barang in barang_sirkulasi_terkini:
        operations.append(
            UpdateOne(
                { "_id": ObjectId(barang["id_barang_sirkulasi_sebelumnya"]) },
                { "$inc": { "jumlah_belum_dikembalikan": -barang["jumlah_dicatat"] } }
            )
        )

    if operations:
        await db.barang_sirkulasi.bulk_write(operations)

async def perbaruiJumlahTerkiniBarang(formulir, barang_raw):
    if formulir["status_sirkulasi"] == "Peminjaman":
        for barang in barang_raw:
            barang["jumlah_dicatat"] = -barang["jumlah_dicatat"]

    operations = [
        UpdateOne(
            {"_id": ObjectId(barang["id"])},
            {
                "$inc": { "jumlah_terkini": barang["jumlah_dicatat"] },
                "$set": {
                    "tanggal_diubah": datetime.now(timezone.utc),
                    "id_pengubah":  formulir["id_pencatat"]
                }
            }
        ) for barang in barang_raw]

    result = await db.barang.bulk_write(operations, ordered=False)
    return result
