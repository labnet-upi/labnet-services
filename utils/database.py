from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from core.config import Settings

settings = Settings()

# Inisialisasi client dan db secara global
client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db]

def convert_objectid(data):
    """
    Rekursif: ubah semua '_id' menjadi 'id' dan konversi ObjectId ke str,
    termasuk dalam dict/list nested.
    """
    if isinstance(data, list):
        return [convert_objectid(item) for item in data]
    
    elif isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            if key == "_id":
                new_data["id"] = convert_objectid(value)
            else:
                new_data[key] = convert_objectid(value)
        return new_data
    
    elif isinstance(data, ObjectId):
        return str(data)
    
    else:
        return data

from bson import ObjectId
import re

def convert_to_objectid(data):
    """
    Rekursif: ubah semua 'id' menjadi '_id' dan konversi string ke ObjectId jika valid,
    termasuk di dalam dict/list nested.
    """
    if isinstance(data, list):
        return [convert_to_objectid(item) for item in data]

    elif isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            if key == "id":
                # Konversi ke _id dan ubah ke ObjectId jika memungkinkan
                new_data["_id"] = convert_to_objectid(value)
            else:
                new_data[key] = convert_to_objectid(value)
        return new_data

    elif isinstance(data, str):
        # Deteksi apakah string adalah ObjectId yang valid
        if re.fullmatch(r"[a-fA-F0-9]{24}", data):
            return ObjectId(data)
        return data

    else:
        return data


def flatten_with_relations(data):
    nodes = []
    relations = []

    def _flatten(node, parentId=None):
        # Salin node tanpa "children" dan tanpa "parentId"
        node_data = {k: v for k, v in node.items() if k != "children"}
        nodes.append(node_data)

        # Simpan relasi jika ada parent
        if parentId is not None:
            relations.append({
                "parentId": parentId,
                "childId": node_data["id"]
            })

        # Proses children (jika ada)
        for child in node.get("children", []):
            _flatten(child, parentId=node_data["id"])

    for root in data:
        _flatten(root)

    return nodes, relations

def filter_top_level_nodes(data):
    # Kumpulkan semua id yang muncul sebagai child
    all_child_ids = set()
    for item in data:
        for child in item.get("children", []):
            all_child_ids.add(child["_id"])

    # Kembalikan hanya node yang bukan anak dari node lain
    return [item for item in data if item["_id"] not in all_child_ids]