import os
import shutil
import uuid
from typing import List

from beanie import PydanticObjectId
from fastapi import HTTPException, UploadFile

from app.models.category_model import Category
from app.models.product_model import Product
from app.models.productVariant_model import ProductVariant
from app.schemas.category_schema import CategorySummaryResponse
from app.schemas.product_schema import ProductCreate, ProductResponse, ProductUpdate
from app.schemas.productVariant_schema import (
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
)


UPLOAD_DIR = "media/products"
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/jfif"]


class ProductService:
    @staticmethod
    async def _get_category_or_raise(category_id: PydanticObjectId) -> Category:
        category = await Category.get(category_id)
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
        return category

    @staticmethod
    async def _get_product_or_raise(product_id: PydanticObjectId) -> Product:
        product = await Product.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    @staticmethod
    def _serialize_variant(variant: ProductVariant) -> ProductVariantResponse:
        return ProductVariantResponse(**variant.model_dump())

    @staticmethod
    def _serialize_product(product: Product, category: Category) -> ProductResponse:
        return ProductResponse(
            _id=product.id,
            name=product.name,
            description=product.description,
            brand=product.brand,
            category=CategorySummaryResponse(_id=category.id, name=category.name),
            variants=[ProductService._serialize_variant(variant) for variant in product.variants],
            starting_price=product.starting_price,
            images=product.images,
            rating=product.rating,
            num_reviews=product.num_reviews,
            specifications=product.specifications,
            is_available=product.is_available,
            is_featured=product.is_featured,
        )

    @staticmethod
    def _ensure_variant_sku_unique(variants: List[ProductVariant]) -> None:
        sku = [variant.sku for variant in variants]
        if len(sku) != len(set(sku)):
            raise HTTPException(status_code=400, detail="Variant SKUs must be unique within a product")

    @staticmethod
    def _build_variant(data: ProductVariantCreate) -> ProductVariant:
        return ProductVariant(**data.model_dump())

    @staticmethod
    def _find_variant_index_or_raise(product: Product, sku: str) -> int:
        for index, variant in enumerate(product.variants):
            if variant.sku == sku:
                return index
        raise HTTPException(status_code=404, detail="Variant not found")

    @staticmethod
    def _merge_variant_update(existing_variant: ProductVariant, data: ProductVariantUpdate) -> ProductVariant:
        update_data = data.model_dump(exclude_unset=True, exclude={"sku"})

        merged_payload = existing_variant.model_dump()
        merged_payload.update(update_data)
        return ProductVariant(**merged_payload)

    @staticmethod
    async def create_product(data: ProductCreate) -> ProductResponse:
        category = await ProductService._get_category_or_raise(data.category_id)

        variants = [ProductService._build_variant(variant) for variant in data.variants]
        ProductService._ensure_variant_sku_unique(variants)

        new_product = Product(
            name=data.name,
            description=data.description,
            brand=data.brand,
            category_id=data.category_id,
            variants=variants,
            rating=data.rating,
            num_reviews=data.num_reviews,
            specifications=data.specifications,
            is_available=data.is_available,
            is_featured=data.is_featured,
        )
        created_product = await new_product.insert()
        return ProductService._serialize_product(created_product, category)

    @staticmethod
    async def add_variant(product_id: PydanticObjectId, data: ProductVariantCreate) -> ProductResponse:
        product = await ProductService._get_product_or_raise(product_id)
        category = await ProductService._get_category_or_raise(product.category_id)

        if any(variant.sku == data.sku for variant in product.variants):
            raise HTTPException(status_code=400, detail="Variant SKU already exists for this product")

        product.variants.append(ProductService._build_variant(data))
        ProductService._ensure_variant_sku_unique(product.variants)
        await product.save()
        return ProductService._serialize_product(product, category)

    @staticmethod
    async def update_variant(
        product_id: PydanticObjectId,
        sku: str,
        data: ProductVariantUpdate,
    ) -> ProductResponse:
        product = await ProductService._get_product_or_raise(product_id)
        category = await ProductService._get_category_or_raise(product.category_id)

        if data.sku != sku:
            raise HTTPException(status_code=400, detail="Variant SKU in path and body must match")

        variant_index = ProductService._find_variant_index_or_raise(product, sku)
        product.variants[variant_index] = ProductService._merge_variant_update(product.variants[variant_index], data)
        await product.save()
        return ProductService._serialize_product(product, category)

    @staticmethod
    async def delete_variant(product_id: PydanticObjectId, sku: str) -> ProductResponse:
        product = await ProductService._get_product_or_raise(product_id)
        category = await ProductService._get_category_or_raise(product.category_id)

        variant_index = ProductService._find_variant_index_or_raise(product, sku)
        product.variants.pop(variant_index)

        if not product.variants:
            raise HTTPException(status_code=400, detail="A product must have at least one variant")

        await product.save()
        return ProductService._serialize_product(product, category)

    @staticmethod
    async def upload_product_images(product_id: PydanticObjectId, images: List[UploadFile]):
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
                raise HTTPException(status_code=400, detail="File too large (Max 5MB).")

            if image.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Rejected {image.filename}. The client sent MIME type: '{image.content_type}'. Allowed types: {ALLOWED_MIME_TYPES}",
                )

            file_ext = os.path.splitext(image.filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)

            image_paths.append(f"/media/products/{unique_filename}")

        product.images = image_paths
        await product.save()
        category = await ProductService._get_category_or_raise(product.category_id)
        return ProductService._serialize_product(product, category)

    @staticmethod
    async def get_all_products():
        products = await Product.find_all().to_list()
        categories = await Category.find_all().to_list()
        category_map = {str(category.id): category for category in categories}
        return [
            ProductService._serialize_product(product, category_map[str(product.category_id)])
            for product in products
        ]

    @staticmethod
    async def get_product(product_id: PydanticObjectId):
        product = await Product.get(product_id)
        if not product:
            return None

        category = await ProductService._get_category_or_raise(product.category_id)
        return ProductService._serialize_product(product, category)

    @staticmethod
    async def update_product(product_id: PydanticObjectId, data: ProductUpdate):
        product = await Product.get(product_id)
        if not product:
            return None

        update_data = data.model_dump(exclude_unset=True)
        category = await ProductService._get_category_or_raise(product.category_id)

        if not update_data:
            return ProductService._serialize_product(product, category)

        if "category_id" in update_data:
            if update_data["category_id"] is None:
                raise HTTPException(status_code=400, detail="category_id cannot be null")
            category = await ProductService._get_category_or_raise(update_data["category_id"])

        if "variants" in update_data:
            raise HTTPException(
                status_code=400,
                detail="Use the dedicated variant endpoints to add, update, or delete variants",
            )

        await product.set(update_data)
        updated_product = await Product.get(product_id)
        return ProductService._serialize_product(updated_product, category)

    @staticmethod
    async def delete_product(product_id: PydanticObjectId):
        product = await Product.get(product_id)
        if not product:
            return False

        for image_path in product.images:
            local_path = image_path.lstrip("/")
            if os.path.exists(local_path):
                os.remove(local_path)

        await product.delete()
        return True
