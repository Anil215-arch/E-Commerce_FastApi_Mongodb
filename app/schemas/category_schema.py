from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import Optional, List
from beanie import PydanticObjectId

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    parent_id: Optional[PydanticObjectId] = None

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    parent_id: Optional[PydanticObjectId] = None

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
