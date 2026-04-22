import pytest
from beanie import PydanticObjectId

from app.core.exceptions import DomainValidationError
from app.models.category_model import Category
from app.models.review_rating_model import ReviewAndRating
from app.models.wishlist_model import Wishlist
from app.schemas.category_schema import CategoryCreate
from app.schemas.review_rating_schema import ReviewCreate
from app.schemas.wishlist_schema import WishlistAddRequest
from app.validators.category_validator import CategoryDomainValidator
from app.validators.review_validator import ReviewDomainValidator
from app.validators.wishlist_validator import WishlistDomainValidator


def test_category_schema_trims_name_before_validation():
    payload = CategoryCreate(name="   Electronics   ")
    assert payload.name == "Electronics"


def test_category_model_rejects_whitespace_name():
    with pytest.raises(ValueError, match="cannot be empty"):
        Category(name="   ")


def test_category_domain_validator_rejects_depth_limit_breach():
    with pytest.raises(DomainValidationError, match="cannot exceed a depth"):
        CategoryDomainValidator.validate_depth_limit(5)


def test_review_schema_trims_review_text():
    payload = ReviewCreate(rating=4, review="   solid quality phone   ", images=[])
    assert payload.review == "solid quality phone"


def test_review_model_rejects_duplicate_images():
    with pytest.raises(ValueError, match="Duplicate images"):
        ReviewAndRating(
            product_id=PydanticObjectId(),
            user_id=PydanticObjectId(),
            rating=4,
            review="Great product overall",
            images=["/img/a.jpg", "/img/a.jpg"],
        )


def test_review_domain_validator_rejects_too_short_text():
    with pytest.raises(DomainValidationError, match="too short"):
        ReviewDomainValidator.validate_review_text("tiny")


def test_wishlist_schema_trims_sku_before_validation():
    payload = WishlistAddRequest(product_id=PydanticObjectId(), sku="   PHX-01   ")
    assert payload.sku == "PHX-01"


def test_wishlist_model_rejects_whitespace_sku():
    with pytest.raises(ValueError, match="SKU cannot be empty"):
        Wishlist(user_id=PydanticObjectId(), product_id=PydanticObjectId(), sku="   ")


def test_wishlist_domain_validator_rejects_empty_sku():
    with pytest.raises(DomainValidationError, match="SKU cannot be empty"):
        WishlistDomainValidator.validate_sku("   ")
