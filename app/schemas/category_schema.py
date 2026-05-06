from pydantic import BaseModel, Field, ConfigDict, field_serializer, model_validator
from typing import Optional, List, Dict
from beanie import PydanticObjectId
from app.core.i18n import CONTENT_TRANSLATION_LANGUAGES


class CategoryTranslationSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def normalize_name(cls, data):
        if isinstance(data, dict) and "name" in data and isinstance(data["name"], str):
            data["name"] = data["name"].strip()
        return data

    model_config = ConfigDict(from_attributes=True)

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    parent_id: Optional[PydanticObjectId] = None
    translations: Optional[Dict[str, CategoryTranslationSchema]] = None
    
    @model_validator(mode="before")
    @classmethod
    def normalize_name(cls, data):
        if isinstance(data, dict) and "name" in data and isinstance(data["name"], str):
            data["name"] = data["name"].strip()
        return data

    @model_validator(mode="after")
    def validate_translations(self):
        if self.translations is not None:
            invalid_langs = [lang for lang in self.translations.keys() if lang not in CONTENT_TRANSLATION_LANGUAGES]
            if invalid_langs:
                raise ValueError("Invalid translation language key.")
        return self

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    parent_id: Optional[PydanticObjectId] = None
    translations: Optional[Dict[str, CategoryTranslationSchema]] = None
    
    @model_validator(mode="before")
    @classmethod
    def normalize_name(cls, data):
        if isinstance(data, dict) and "name" in data and isinstance(data["name"], str):
            data["name"] = data["name"].strip()
        return data

    @model_validator(mode="after")
    def validate_translations(self):
        if self.translations is not None:
            invalid_langs = [lang for lang in self.translations.keys() if lang not in CONTENT_TRANSLATION_LANGUAGES]
            if invalid_langs:
                raise ValueError("Invalid translation language key.")
        return self

class CategoryResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    name: str
    parent_id: Optional[PydanticObjectId] = None

    @field_serializer("id", "parent_id")
    def serialize_object_ids(self, value):
        return str(value) if value else None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class CategorySummaryResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    name: str

    @field_serializer("id")
    def serialize_object_id(self, value):
        return str(value)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class CategoryTreeResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    name: str
    parent_id: Optional[PydanticObjectId] = None
    children: List["CategoryTreeResponse"] = Field(default_factory=list)

    @field_serializer("id", "parent_id")
    def serialize_object_ids(self, value):
        return str(value) if value else None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

CategoryTreeResponse.model_rebuild()


class CategoryManageResponse(CategoryResponse):
    translations: Dict[str, CategoryTranslationSchema] = Field(default_factory=dict)
