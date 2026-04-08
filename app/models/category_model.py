from beanie import Document, PydanticObjectId
from pydantic import Field
from typing import Optional
from pymongo import IndexModel, ASCENDING

class Category(Document):
    name: str = Field(..., min_length=2, max_length=100)
    parent_id: Optional[PydanticObjectId] = None

    class Settings:
        name = "categories"
        indexes = [
            IndexModel([("parent_id", ASCENDING)]),
        ]
