from pydantic import BaseModel, Field
from typing import Optional

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    category: str

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None