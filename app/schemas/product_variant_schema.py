from typing import Dict, Optional
from pydantic import BaseModel, Field, model_validator, ConfigDict

from app.core.i18n import CONTENT_TRANSLATION_LANGUAGES


class ProductVariantTranslationSchema(BaseModel):
    attributes: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_attributes(cls, data):
        if isinstance(data, dict) and "attributes" in data and isinstance(data["attributes"], dict):
            data["attributes"] = {
                str(key).strip(): str(value).strip()
                for key, value in data["attributes"].items()
                if str(key).strip()
            }
        return data

    model_config = ConfigDict(from_attributes=True)
    
class ProductVariantCreate(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    price: int = Field(..., gt=0)
    discount_price: Optional[int] = Field(None, gt=0)
    
    available_stock: int = Field(..., ge=0)
    reserved_stock: int = Field(0, ge=0)
    attributes: Dict[str, str] = Field(default_factory=dict)
    translations: Optional[Dict[str, ProductVariantTranslationSchema]] = None
    
    @model_validator(mode="after")
    def validate_discount_price(self):
        if self.discount_price is not None and self.discount_price >= self.price:
            raise ValueError("discount_price must be less than price")
        return self
    
    @model_validator(mode="after")
    def validate_translations(self):
        if self.translations is not None:
            invalid_langs = [
                lang for lang in self.translations.keys()
                if lang not in CONTENT_TRANSLATION_LANGUAGES
            ]
            if invalid_langs:
                raise ValueError("Invalid translation language key.")
        return self
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sku": "APPLE-MBA-M2-256",
                "price": 99999,
                "discount_price": 19999,
                "available_stock": 10,
                "reserved_stock": 0,
                "attributes": {
                    "Processor": "Apple M2",
                    "RAM": "8GB",
                    "Storage": "256GB SSD"
                },
                "translations": {
                    "hi": {
                        "attributes": {
                            "Processor": "एप्पल M2 प्रोसेसर",
                            "RAM": "8GB रैम",
                            "Storage": "256GB SSD स्टोरेज"
                        }
                    },
                    "ja": {
                        "attributes": {
                            "Processor": "Apple M2プロセッサ",
                            "RAM": "8GBメモリ",
                            "Storage": "256GB SSDストレージ"
                        }
                    }
                }
            }
        }
    )



class ProductVariantUpdate(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    price: Optional[int] = Field(None, gt=0)
    discount_price: Optional[int] = Field(None, gt=0)
    available_stock: Optional[int] = Field(None, ge=0)
    reserved_stock: Optional[int] = Field(None, ge=0)
    attributes: Optional[Dict[str, str]] = None
    translations: Optional[Dict[str, ProductVariantTranslationSchema]] = None

    @model_validator(mode="after")
    def validate_discount_price(self):
        if self.discount_price is not None and self.price is not None and self.discount_price >= self.price:
            raise ValueError("discount_price must be less than price")
        return self
    
    @model_validator(mode="after")
    def validate_translations(self):
        if self.translations is not None:
            invalid_langs = [
                lang for lang in self.translations.keys()
                if lang not in CONTENT_TRANSLATION_LANGUAGES
            ]
            if invalid_langs:
                raise ValueError("Invalid translation language key.")
        return self

class ProductVariantResponse(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    price: int = Field(..., gt=0)
    discount_price: Optional[int] = Field(None, gt=0)
    
    available_stock: int = Field(..., ge=0)
    reserved_stock: int = Field(..., ge=0)
    attributes: Dict[str, str] = Field(default_factory=dict)
