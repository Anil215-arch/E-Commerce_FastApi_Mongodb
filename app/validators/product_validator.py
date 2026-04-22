from typing import Dict, Optional, List
from app.core.exceptions import DomainValidationError

class ProductDomainValidator:
    
    @staticmethod
    def validate_variant_data(
        price: int, 
        discount_price: Optional[int], 
        available_stock: int, 
        reserved_stock: int, 
        attributes: Dict[str, str]
    ) -> None:
        """Validates the math and structural integrity of a single variant."""
        if discount_price is not None and discount_price >= price:
            raise DomainValidationError("Discount price must be strictly less than the base price.")
        
        if reserved_stock > available_stock:
            raise DomainValidationError("Reserved stock cannot exceed available stock.")

        if attributes:
            for k, v in attributes.items():
                key = str(k).strip()
                if not key:
                    raise DomainValidationError("Attribute keys cannot be empty.")
                if len(key) > 50 or len(str(v)) > 200:
                    raise DomainValidationError("Attribute size exceeded: keys <= 50, values <= 200 chars.")

    @staticmethod
    def validate_specifications(specifications: Dict[str, str]) -> None:
        """Validates the structural integrity of product specifications."""
        if not specifications:
            return
            
        for k, v in specifications.items():
            key = str(k).strip()
            if not key:
                raise DomainValidationError("Specification keys cannot be empty.")
            if len(key) > 50 or len(str(v)) > 500:
                raise DomainValidationError("Specification size exceeded: keys <= 50, values <= 500 chars.")
            

    @staticmethod
    def validate_images(images: List[str]) -> None:
        """Validates the structural integrity of image URL arrays."""
        if not images:
            return

        seen_images = set()
        for img in images:
            img_str = str(img).strip()
            
            if not img_str:
                raise DomainValidationError("Empty image URL not allowed.")
                
            if len(img_str) > 500:
                raise DomainValidationError("Image URL size exceeded (max 500 chars).")
                
            if img_str in seen_images:
                raise DomainValidationError("Duplicate image URLs are not allowed.")
                
            seen_images.add(img_str)