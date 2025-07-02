from typing import Optional
from typing import Literal
from bson import ObjectId
from pymongo import UpdateOne, InsertOne, DeleteOne
from datetime import datetime, timezone
from utils.database import db
import copy
from core.logger import logger

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

def getPipeLineFormSirkulasi(id_formulir: Optional[str] = None):
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

async def upsertFormulirSirkulasiBarang(data_penanggung_jawab, object_user_id, is_insert: bool):
    pj = data_penanggung_jawab
    id_formulir = ObjectId(pj["id"])
    now_iso = datetime.fromisoformat(pj["tanggal"]).isoformat()

    formulir_common = {
        "nama": pj["nama"],
        "notel": pj["notel"],
        "keterangan": pj["keterangan"],
        "status_sirkulasi": pj["status_sirkulasi"],
        "id_pengubah": object_user_id,
        "tanggal_perubahan": now_iso,
        **(
            {"sudah_dikembalikan_semua": False}
            if pj["status_sirkulasi"] == "peminjaman"
            else {"id_formulir_sebelumnya": ObjectId(pj["id_formulir_sebelumnya"])}
        )
    }

    # Tambahkan ini hanya kalau insert
    if is_insert:
        formulir_common["id_pencatat"] = object_user_id
        formulir_common["tanggal_pencatatan"] = now_iso

    result = await db.formulir_sirkulasi_barang.update_one(
        {"_id": id_formulir},
        {"$set": formulir_common},
        upsert=True
    )

    return {**formulir_common, "_id": id_formulir}, id_formulir


async def perbaruStatusPengembalianBarang(id_formulir):
    pipeline = getPipeLineFormSirkulasi(id_formulir)
    logger.debug("pipeline", pipeline)
    logger.debug("id_formulir", id_formulir)
    cursor = db.formulir_sirkulasi_barang.aggregate(pipeline)
    result = await cursor.to_list(length=1)
    result = result[0]

    data_barang_sirkulasi = result["data_barang_sirkulasi"]
    logger.debug("data_barang_sirkulasi", data_barang_sirkulasi)
    sudahDikembalikanSemua = all(
        barang_sirkulasi["jumlah_belum_dikembalikan"] == 0 for barang_sirkulasi in data_barang_sirkulasi
    )
    if sudahDikembalikanSemua:
        db.formulir_sirkulasi_barang.update_one(
            {"_id": ObjectId(id_formulir)},
            {
                "$set": { "sudah_dikembalikan_semua": True }
            }
        )
    return sudahDikembalikanSemua
    

async def upsertBarangSirkulasi(barang_raw, formulir, id_formulir):
    operations = []
    update_docs = []

    for barang in barang_raw:
        filter_query = {
            "id_formulir": id_formulir,
            "id_barang": ObjectId(barang["id"])
        }

        update_doc = {
            "$set": {
                "status_sirkulasi": formulir["status_sirkulasi"],
                "keterangan": barang.get("keterangan", ""),
                "jumlah_dicatat": barang.get("jumlah_dicatat", 0),
            }
        }

        if formulir["status_sirkulasi"] == "pengembalian" and "id_barang_sirkulasi_sebelumnya" in barang:
            update_doc["$set"]["id_barang_sirkulasi_sebelumnya"] = ObjectId(barang["id_barang_sirkulasi_sebelumnya"])
        else:
            update_doc["$set"]["jumlah_belum_dikembalikan"] = barang.get("jumlah_dicatat", 0)

        operations.append(UpdateOne(filter_query, update_doc, upsert=True))
        update_docs.append({
            "id": barang["id"],
            "status_sirkulasi": formulir["status_sirkulasi"],
            "keterangan": barang.get("keterangan", ""),
            "jumlah_dicatat": barang.get("jumlah_dicatat", 0),
            **(
                {"id_barang_sirkulasi_sebelumnya": barang["id_barang_sirkulasi_sebelumnya"]}
                if formulir["status_sirkulasi"] == "pengembalian" and "id_barang_sirkulasi_sebelumnya" in barang
                else {"jumlah_belum_dikembalikan": barang.get("jumlah_dicatat", 0)}
            )
        })

    if operations:
        await db.barang_sirkulasi.bulk_write(operations)

    return update_docs

async def perbaruiJumlahBelumDikembalikanBarangSirkulasi(barang_sirkulasi_terkini, positif):
    if not positif:
        for barang in barang_sirkulasi_terkini:
            barang["jumlah_dicatat"] = -barang["jumlah_dicatat"]

    operations = []
    for barang in barang_sirkulasi_terkini:
        operations.append(
            UpdateOne(
                { "_id": ObjectId(barang["id_barang_sirkulasi_sebelumnya"]) },
                { "$inc": { "jumlah_belum_dikembalikan": barang["jumlah_dicatat"] } }
            )
        )
    
    result = {}
    if operations:
        result = await db.barang_sirkulasi.bulk_write(operations)
        logger.debug("berjalan")
    
    return result

async def perbaruiJumlahTerkiniBarang(formulir, barang_raw, positif, keyname):
    barang_copy = copy.deepcopy(barang_raw)
    if not positif:
        for barang in barang_copy:
            barang["jumlah_dicatat"] = -barang["jumlah_dicatat"]

    operations = [
        UpdateOne(
            {"_id": ObjectId(barang[keyname])},
            {
                "$inc": { "jumlah_terkini": barang["jumlah_dicatat"] },
                "$set": {
                    "tanggal_diubah": datetime.now(timezone.utc),
                    "id_pengubah":  formulir["id_pencatat"]
                }
            }
        ) for barang in barang_copy]
    result = {}
    if operations:
        result = await db.barang.bulk_write(operations, ordered=False)
        logger.debug("berjalan")

    return result


async def getDataBarangSirkulasiByFormulir(id_formulir: str):
    pipeline = [{"$match": {"id_formulir": ObjectId(id_formulir)}}]
    cursor = db.barang_sirkulasi.aggregate(pipeline)
    result = await cursor.to_list(length=None)
    return result

async def getBarangBerisisan(barang_sirkulasi_ids):
    pipeline = get_barang_pipeline()
    pipeline = [{ "$match": { "$expr": { "$in": ["$_id", barang_sirkulasi_ids] } } }] + pipeline
    cursor = db.barang.aggregate(pipeline)
    result = await cursor.to_list(length=None)
    return result

async def getBarangTidakDipinjam():
    pipeline = get_barang_pipeline("tidak_dipinjam")
    cursor = db.barang_aktif.aggregate(pipeline)
    result = await cursor.to_list(length=None)
    return result

async def getDataBarangSirkulasi(id_formulir: str, is_peminjaman: bool):
    #get data barang_sirkulasi yang id_formulirnya sama
    barang_sirkulasi = await getDataBarangSirkulasiByFormulir(id_formulir)
    dict_barang_sirkulasi = {str(item["id_barang"]): item for item in barang_sirkulasi}

    #tampung deret id barang dari barang_sirkulasi
    barang_sirkulasi_ids = [item['id_barang'] for item in barang_sirkulasi]

    #get data barang yang left join seperti di barang, tapi idnya dari yg tadi
    barang_berisisan = await getBarangBerisisan(barang_sirkulasi_ids)

    #lenkapi data
    def setDataBarang(list_barang):
        for barang in list_barang:
            barang_sirkulasi_founded = dict_barang_sirkulasi[str(barang["_id"])]
            barang["id_barang_sirkulasi_sebelumnya"] = barang_sirkulasi_founded["_id"]
            # barang["id_barang_sirkulasi_sebelumnya"] = barang_sirkulasi_founded["id_barang_sirkulasi_sebelumnya"]
            barang["keterangan"] = barang_sirkulasi_founded["keterangan"]
            barang["jumlah_dicatat"] = barang_sirkulasi_founded["jumlah_dicatat"]
            barang["checked"] = True
            barang["jumlah_belum_dikembalikan"] = barang_sirkulasi_founded["jumlah_belum_dikembalikan"]
            if is_peminjaman:
                barang["jumlah_maks_dapat_dicatat"] = barang["jumlah_terkini"] + barang_sirkulasi_founded["jumlah_dicatat"]
            
            if barang.get("children", False) and len(barang["children"]) > 0:
                barang["children"] = setDataBarang(barang["children"])
        return list_barang
    result = setDataBarang(barang_berisisan)

    #untuk peminjaman, concat juga data tidak dipinjam
    if is_peminjaman:
        barang_tidak_dipinjam = await getBarangTidakDipinjam()
        for item in barang_tidak_dipinjam:
            item["jumlah_maks_dapat_dicatat"] = item["jumlah_terkini"]
            item["jumlah_dicatat"] = item["jumlah_terkini"]
            
            # Lengkapi juga bagian children jika ada
            if "children" in item and isinstance(item["children"], list):
                for child in item["children"]:
                    child["jumlah_maks_dapat_dicatat"] = child.get("jumlah_terkini", 0)
                    child["jumlah_dicatat"] = child.get("jumlah_terkini", 0)

        result = result + barang_tidak_dipinjam

    return result

async def getFormulirSirkulasi(id_formulir):
    pipeline = [
        {"$match": { "_id": ObjectId(id_formulir)}}
    ]
    cursor = db.formulir_sirkulasi_barang.aggregate(pipeline)
    result = await cursor.to_list(length=1)
    return result[0]

async def kembalikanJumlahTerkiniBarang(formulir):
    cursor_barang_sirkulasi = db.barang_sirkulasi.aggregate([{"$match": { "id_formulir": formulir["_id"]}}])
    barang_sirkulasi = await cursor_barang_sirkulasi.to_list(length=None)
    result = await perbaruiJumlahTerkiniBarang(formulir, barang_sirkulasi, formulir["status_sirkulasi"] == "peminjaman", "id_barang")
    return result.modified_count if result.modified_count else 0

async def hapusBarangSirkulasi(id_formulir: ObjectId):
    result = await db.barang_sirkulasi.delete_many({"id_formulir": id_formulir})
    return result.deleted_count if result.deleted_count else 0

async def hapusFormulirSirkulasi(id_formulir: ObjectId):
    result = await db.formulir_sirkulasi_barang.delete_one({"_id": id_formulir})
    return result.deleted_count if result.deleted_count else 0

async def perbaruiStatusDikembalikanFormulirSirkulasi(id_formulir: ObjectId):
    result = await db.formulir_sirkulasi_barang.update_one(
        {"_id": id_formulir},
        {
            "$set": { "sudah_dikembalikan_semua": False }
        }
    )
    return result.modified_count if result.modified_count else 0

async def kembalikanJumlahBarangSirkulasi(id_formulir: ObjectId):
    cursor_barang_sirkulasi_pengembalian = db.barang_sirkulasi.aggregate([{"$match":{"id_formulir": id_formulir}}])
    barang_sirkulasi_pengembalian = await cursor_barang_sirkulasi_pengembalian.to_list(length=None)
    result = await perbaruiJumlahBelumDikembalikanBarangSirkulasi(barang_sirkulasi_pengembalian, True)
    return result.modified_count if result.modified_count else 0

async def perbaruiDanSinkronisasiBarang(formulir, body):
    operations_barang_sirkulasi = []
    operations_barang = []

    # Data baru dari request
    data_barang_sirkulasi_baru = body["barang"]
    dict_barang_sirkulasi_baru = {str(item["id"]): item for item in data_barang_sirkulasi_baru}
    logger.debug("Barang sirkulasi baru:", dict_barang_sirkulasi_baru)

    # Data lama dari database
    data_barang_sirkulasi_lama = await getDataBarangSirkulasiByFormulir(str(formulir["_id"]))
    dict_barang_sirkulasi_lama = {str(item["_id"]): item for item in data_barang_sirkulasi_lama}
    logger.debug("Barang sirkulasi lama:", dict_barang_sirkulasi_lama)

    # Tangani barang yang baru (insert atau update)
    for id_baru, barang_baru in dict_barang_sirkulasi_baru.items():
        if id_baru in dict_barang_sirkulasi_lama:
            barang_lama = dict_barang_sirkulasi_lama[id_baru]
            selisih = barang_lama["jumlah_dicatat"] - barang_baru["jumlah_dicatat"]
            logger.debug(f"Update: ID {id_baru}, selisih: {selisih}")
            if selisih != 0:
                operations_barang.append(
                    UpdateOne(
                        { "_id": ObjectId(barang_baru["id"]) },
                        { "$inc": { "jumlah_terkini": selisih } }
                    )
                )
                # (Opsional) update keterangan/jumlah di koleksi barang_sirkulasi jika dibutuhkan
                operations_barang_sirkulasi.append(
                    UpdateOne(
                        { "_id": ObjectId(id_baru) },
                        { "$set": {
                            "jumlah_dicatat": barang_baru["jumlah_dicatat"],
                            "keterangan": barang_baru.get("keterangan", "")
                        }}
                    )
                )
        else:
            # Data baru → insert barang_sirkulasi dan update jumlah_terkini
            logger.debug(f"Insert baru: ID {id_baru}")
            operations_barang_sirkulasi.append(
                InsertOne({
                    "id_formulir": ObjectId(formulir["_id"]),
                    "id_barang": ObjectId(barang_baru["id"]),
                    "jumlah_dicatat": barang_baru["jumlah_dicatat"],
                    "status_sirkulasi": formulir["status_sirkulasi"],
                    "keterangan": barang_baru.get("keterangan", "")
                })
            )
            operations_barang.append(
                UpdateOne(
                    { "_id": ObjectId(barang_baru["id"]) },
                    { "$inc": { "jumlah_terkini": -barang_baru["jumlah_dicatat"] } }
                )
            )

    # Tangani barang yang dihapus dari form
    for id_lama, barang_lama in dict_barang_sirkulasi_lama.items():
        if id_lama not in dict_barang_sirkulasi_baru:
            logger.debug(f"Delete: ID {id_lama}")
            operations_barang_sirkulasi.append(
                DeleteOne({ "_id": ObjectId(id_lama) })
            )
            operations_barang.append(
                UpdateOne(
                    { "_id": ObjectId(barang_lama["id_barang"]) },
                    { "$inc": { "jumlah_terkini": barang_lama["jumlah_dicatat"] } }
                )
            )

    # Log operasi sebelum eksekusi
    logger.debug("Operasi barang_sirkulasi:", operations_barang_sirkulasi)
    logger.debug("Operasi barang:", operations_barang)

    # Eksekusi bulk
    if operations_barang_sirkulasi:
        await db.barang_sirkulasi.bulk_write(operations_barang_sirkulasi)
    if operations_barang:
        await db.barang.bulk_write(operations_barang)

    return {
        "barang_sirkulasi": {
            "inserted": sum(1 for op in operations_barang_sirkulasi if isinstance(op, InsertOne)),
            "updated": sum(1 for op in operations_barang_sirkulasi if isinstance(op, UpdateOne)),
            "deleted": sum(1 for op in operations_barang_sirkulasi if isinstance(op, DeleteOne)),
        },
        "barang": {
            "updated": len(operations_barang)
        }
    }

async def getListSirkulasi():
    pipeline = getPipeLineFormSirkulasi()
    cursor = db.formulir_sirkulasi_barang.aggregate(pipeline)
    result = await cursor.to_list(length=None)
    return result


async def sync_barang_hirarki(parentId: ObjectId, barang_hirarki_baru: list):
    # Ambil data relasi lama dari database
    cursor = db.barang_hirarki.find({"parentId": parentId})
    barang_hirarki_lama = await cursor.to_list(length=None)

    # Konversi relasi menjadi set of tuples (parentId, childId) agar mudah dibandingkan
    set_lama = set((str(rel["parentId"]), str(rel["childId"])) for rel in barang_hirarki_lama)
    set_baru = set((str(parentId), str(child["id"])) for child in barang_hirarki_baru)

    # Cari yang perlu di-insert (baru, tapi belum ada)
    to_insert = set_baru - set_lama
    # Cari yang perlu dihapus (lama, tapi tidak ada di baru)
    to_delete = set_lama - set_baru


    bulk_ops = []

    # Siapkan operasi insert
    for parent, child in to_insert:
        bulk_ops.append(InsertOne({
            "parent_id": ObjectId(parent),
            "child_id": ObjectId(child)
        }))

    # Siapkan operasi delete
    for parent, child in to_delete:
        bulk_ops.append(DeleteOne({
            "parent_id": ObjectId(parent),
            "child_id": ObjectId(child)
        }))

    # Eksekusi bulk jika ada operasi
    if bulk_ops:
        result = await db.barang_hirarki.bulk_write(bulk_ops)
        return {
            "inserted_count": result.inserted_count,
            "deleted_count": result.deleted_count
        }

    return {
        "inserted_count": 0,
        "deleted_count": 0
    }
