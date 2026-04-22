from beanie import Document, PydanticObjectId
from pydantic import Field, model_validator
from typing import Optional
from pymongo import IndexModel, ASCENDING
from app.models.base_model import AuditDocument

class Category(AuditDocument):
    name: str = Field(..., min_length=2, max_length=100)
    parent_id: Optional[PydanticObjectId] = None
    
    @model_validator(mode="after")
    def validate_category(self):
        if not self.name.strip():
            raise ValueError("Category name cannot be empty or whitespace")

        if self.parent_id is not None and self.id is not None and self.parent_id == self.id:
            raise ValueError("A category cannot be its own parent")

        return self
    
    class Settings:
        name = "categories"
        indexes = [
            IndexModel([("parent_id", ASCENDING)]),
        ]
