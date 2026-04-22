from typing import List, Optional
from app.core.exceptions import DomainValidationError

class ReviewDomainValidator:
    MAX_IMAGES = 5  # Hard limit to prevent NoSQL array bloat

    @staticmethod
    def validate_review_text(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
            
        clean_text = text.strip()
        if not clean_text:
            raise DomainValidationError("Review text cannot consist only of whitespace.")
        if len(clean_text) < 5:
            raise DomainValidationError("Review text is too short. Please provide a meaningful review.")
            
        return clean_text

    @staticmethod
    def validate_images(images: List[str]) -> List[str]:
        if len(images) > ReviewDomainValidator.MAX_IMAGES:
            raise DomainValidationError(
                f"You cannot upload more than {ReviewDomainValidator.MAX_IMAGES} images per review."
            )
        # Deduplicate URLs to prevent UI glitching
        for img in images:
            img_str = str(img).strip()
            if not img_str:
                raise DomainValidationError("Image value cannot be empty.")
            if len(img_str) > 500:
                raise DomainValidationError("Image value is too long.")
            
        return list(dict.fromkeys(images))