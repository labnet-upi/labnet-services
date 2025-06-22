# routers/inventaris.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from database import db

router = APIRouter()

class Item(BaseModel):
    name: str
    quantity: int

class ItemOut(Item):
    id: str

@router.get("/", response_model=List[ItemOut])
async def get_items():
    items_cursor = db.inventaris.find()
    items = []
    async for item in items_cursor:
        item["id"] = str(item["_id"])
        items.append(ItemOut(**item))
    return items

@router.post("/", response_model=ItemOut)
async def create_item(item: Item):
    result = await db.inventaris.insert_one(item.dict())
    new_item = await db.inventaris.find_one({"_id": result.inserted_id})
    new_item["id"] = str(new_item["_id"])
    return ItemOut(**new_item)
