from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
from bson import ObjectId

MONGO_URI = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_URI)
db = client.main_service

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
            # Ganti key '_id' jadi 'id' dan convert isinya
            if key == "_id":
                new_data["_id"] = convert_objectid(value)
            else:
                new_data[key] = convert_objectid(value)
        return new_data
    
    elif isinstance(data, ObjectId):
        return str(data)
    
    else:
        return data
