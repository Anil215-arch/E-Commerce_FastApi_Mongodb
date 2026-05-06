from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any
from pymongo import IndexModel, ASCENDING
from app.models.base_model import AuditDocument


class CategoryTranslation(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def normalize_name(cls, data: Any):
        if isinstance(data, dict) and "name" in data and isinstance(data["name"], str):
            data["name"] = data["name"].strip()
        return data

class Category(AuditDocument):
    name: str = Field(..., min_length=2, max_length=100)
    parent_id: Optional[PydanticObjectId] = None
    translations: Dict[str, CategoryTranslation] = Field(default_factory=dict)
    
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
