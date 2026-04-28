import os
import shutil
import uuid
from typing import cast
from typing import List
from app.validators.product_validator import ProductDomainValidator
from beanie import PydanticObjectId
from fastapi import HTTPException, UploadFile
from app.utils.product_mapper import ProductMapper
from app.models.category_model import Category
from app.models.product_model import Product, ProductTranslation
from app.models.product_variant_model import ProductVariant
from app.schemas.category_schema import CategorySummaryResponse
from app.schemas.product_schema import ProductCreate, ProductManageResponse, ProductResponse, ProductUpdate
from app.schemas.product_variant_schema import (
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
)
from app.services.wishlist_services import WishlistService
from app.core.message_keys import Msg


UPLOAD_DIR = "media/products"
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/jfif"]


class ProductService:
    @staticmethod
    async def _get_category_or_raise(category_id: PydanticObjectId) -> Category:
        category = await Category.get(category_id)
        if not category:
            raise HTTPException(status_code=400, detail=Msg.CATEGORY_NOT_FOUND)
        return category

    @staticmethod
    async def _get_product_or_raise(product_id: PydanticObjectId) -> Product:
        product = await Product.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail=Msg.PRODUCT_NOT_FOUND)
        return product

    @staticmethod
    def _serialize_variant(variant: ProductVariant) -> ProductVariantResponse:
        return ProductVariantResponse(**variant.model_dump())


    @staticmethod
    def _build_variant(data: ProductVariantCreate) -> ProductVariant:
        return ProductVariant(**data.model_dump())

    @staticmethod
    def _find_variant_index_or_raise(product: Product, sku: str) -> int:
        for index, variant in enumerate(product.variants):
            if variant.sku == sku:
                return index
        raise HTTPException(status_code=404, detail=Msg.VARIANT_NOT_FOUND)

    @staticmethod
    def _merge_variant_update(existing_variant: ProductVariant, data: ProductVariantUpdate) -> ProductVariant:
        merged_payload = existing_variant.model_dump()
        update_data = data.model_dump(exclude_unset=True, exclude={"sku"})

        if "translations" in update_data and update_data["translations"] is not None:
            merged_payload["translations"] = update_data["translations"]
            update_data.pop("translations")

        merged_payload.update(update_data)
        return ProductVariant(**merged_payload)

    @staticmethod
    async def create_product(data: ProductCreate, current_user_id: PydanticObjectId) -> ProductManageResponse:
        category = await ProductService._get_category_or_raise(data.category_id)
        
        ProductDomainValidator.validate_specifications(data.specifications)
        for v in data.variants:
            ProductDomainValidator.validate_variant_data(
                price=v.price, 
                discount_price=v.discount_price, 
                available_stock=v.available_stock, 
                reserved_stock=v.reserved_stock, 
                attributes=v.attributes     
            )
            
        variants = [ProductService._build_variant(variant) for variant in data.variants]
        translations = {
            lang: ProductTranslation(**translated.model_dump())
            for lang, translated in (data.translations or {}).items()
        }

        new_product = Product(
            name=data.name,
            description=data.description,
            brand=data.brand,
            category_id=data.category_id,
            translations=translations,
            variants=variants,
            specifications=data.specifications,
            is_available=data.is_available,
            is_featured=data.is_featured,
            created_by=current_user_id,
            updated_by=current_user_id
        )
        created_product = await new_product.insert()
        return cast(ProductManageResponse, ProductMapper.serialize_product(created_product, category, include_translations=True))

    @staticmethod
    async def add_variant(product_id: PydanticObjectId, data: ProductVariantCreate, current_user_id: PydanticObjectId) -> ProductManageResponse:
        ProductDomainValidator.validate_variant_data(
            price=data.price, 
            discount_price=data.discount_price, 
            available_stock=data.available_stock, 
            reserved_stock=data.reserved_stock, 
            attributes=data.attributes
        )
        product = await ProductService._get_product_or_raise(product_id)
        category = await ProductService._get_category_or_raise(product.category_id)

        if any(variant.sku == data.sku for variant in product.variants):
            raise HTTPException(status_code=400, detail=Msg.VARIANT_SKU_ALREADY_EXISTS)

        product.variants.append(ProductService._build_variant(data))
        product.updated_by = current_user_id
        await product.save()
        return cast(ProductManageResponse, ProductMapper.serialize_product(product, category, include_translations=True))

    @staticmethod
    async def update_variant(
        product_id: PydanticObjectId,
        sku: str,
        data: ProductVariantUpdate,
        current_user_id: PydanticObjectId
    ) -> ProductManageResponse:
        product = await ProductService._get_product_or_raise(product_id)
        category = await ProductService._get_category_or_raise(product.category_id)

        if data.sku and data.sku != sku:
            raise HTTPException(status_code=400, detail=Msg.VARIANT_SKU_PATH_BODY_MISMATCH)

        variant_index = ProductService._find_variant_index_or_raise(product, sku)
        merged_variant = product.variants[variant_index] = ProductService._merge_variant_update(product.variants[variant_index], data)
        ProductDomainValidator.validate_variant_data(
            price=merged_variant.price,
            discount_price=merged_variant.discount_price,
            available_stock=merged_variant.available_stock,
            reserved_stock=merged_variant.reserved_stock,
            attributes=merged_variant.attributes
        )
        product.updated_by = current_user_id
        await product.save()
        return cast(ProductManageResponse, ProductMapper.serialize_product(product, category, include_translations=True))

    @staticmethod
    async def delete_variant(product_id: PydanticObjectId, sku: str, current_user_id: PydanticObjectId) -> ProductManageResponse:
        product = await ProductService._get_product_or_raise(product_id)
        category = await ProductService._get_category_or_raise(product.category_id)

        variant_index = ProductService._find_variant_index_or_raise(product, sku)
        product.variants.pop(variant_index)
        product.updated_by = current_user_id

        if not product.variants:
            raise HTTPException(status_code=400, detail=Msg.PRODUCT_REQUIRES_AT_LEAST_ONE_VARIANT)

        await product.save()
        await WishlistService.remove_ghost_product_references(product_id, sku)
        return cast(ProductManageResponse, ProductMapper.serialize_product(product, category, include_translations=True))

    @staticmethod
    async def upload_product_images(product_id: PydanticObjectId, images: List[UploadFile], current_user_id: PydanticObjectId):
        product = await Product.get(product_id)
        if not product:
            return None

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        image_paths = product.images.copy()

        for image in images:
            image.file.seek(0, os.SEEK_END)
            file_size = image.file.tell()
            image.file.seek(0)

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail=Msg.FILE_TOO_LARGE_MAX_5MB)

            if image.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=Msg.INVALID_IMAGE_MIME_TYPE,
                )

            signature = image.file.read(16)
            image.file.seek(0)
            if image.content_type in {"image/jpeg", "image/jfif"} and not signature.startswith(b"\xff\xd8\xff"):
                raise HTTPException(status_code=400, detail=Msg.INVALID_JPEG_FILE_SIGNATURE)
            if image.content_type == "image/png" and not signature.startswith(b"\x89PNG\r\n\x1a\n"):
                raise HTTPException(status_code=400, detail=Msg.INVALID_PNG_FILE_SIGNATURE)

            safe_filename = image.filename or "unknown_image"
            file_ext = os.path.splitext(safe_filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)

            image_paths.append(f"/media/products/{unique_filename}")
            
        ProductDomainValidator.validate_images(image_paths)
        product.images = image_paths
        product.updated_by = current_user_id
        await product.save()
        category = await ProductService._get_category_or_raise(product.category_id)
        return ProductMapper.serialize_product(product, category, include_translations=True)

    @staticmethod
    async def update_product(product_id: PydanticObjectId, data: ProductUpdate, current_user_id: PydanticObjectId):
        product = await Product.get(product_id)
        if not product:
            return None

        update_data = data.model_dump(exclude_unset=True)
        category = await ProductService._get_category_or_raise(product.category_id)

        if not update_data:
            return ProductMapper.serialize_product(product, category, include_translations=True)
        
        if "specifications" in update_data:
            ProductDomainValidator.validate_specifications(update_data["specifications"])
        
        if "images" in update_data:
            ProductDomainValidator.validate_images(update_data["images"])
            
        if "category_id" in update_data:
            if update_data["category_id"] is None:
                raise HTTPException(status_code=400, detail=Msg.CATEGORY_ID_CANNOT_BE_NULL)
            category = await ProductService._get_category_or_raise(update_data["category_id"])

        if "variants" in update_data:
            raise HTTPException(
                status_code=400,
                detail=Msg.PRODUCT_VARIANTS_UPDATE_USE_DEDICATED_ENDPOINTS,
            )
            
        update_data["updated_by"] = current_user_id
        await product.set(update_data)
        updated_product = await Product.get(product_id)
        if not updated_product:
            raise HTTPException(status_code=404, detail=Msg.PRODUCT_NOT_FOUND_AFTER_UPDATE)

        if update_data.get("is_available") is False:
            await WishlistService.remove_ghost_product_references(product_id)
            
        return ProductMapper.serialize_product(updated_product, category, include_translations=True)

    @staticmethod
    async def delete_product(product_id: PydanticObjectId, current_user_id: PydanticObjectId):
        product = await Product.get(product_id)
        if not product or product.is_deleted:
            return False

        for image_path in product.images:
            local_path = image_path.lstrip("/")
            if os.path.exists(local_path):
                os.remove(local_path)

        await product.soft_delete(current_user_id)
        await WishlistService.remove_ghost_product_references(product_id)
        return True
