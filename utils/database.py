from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from config import Settings

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
