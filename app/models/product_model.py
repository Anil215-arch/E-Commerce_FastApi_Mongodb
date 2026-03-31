from typing import Optional
from beanie import Document
from pydantic import Field

class Product(Document):
    name: str = Field(..., min_length=3, max_length=100)
    description: str
    price: float = Field(..., gt=0)
    category: str

    class Settings:
        name = "products" 