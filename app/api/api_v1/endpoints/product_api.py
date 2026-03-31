from fastapi import APIRouter, HTTPException, status
from app.schemas.product_schema import ProductCreate, ProductUpdate
from app.services.product_services import ProductService
from beanie import PydanticObjectId

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create(product: ProductCreate):
    return await ProductService.create_product(product)

@router.get("/")
async def read_all():
    return await ProductService.get_all_products()

@router.get("/{id}")
async def read_one(id: PydanticObjectId):
    product = await ProductService.get_product(id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/{id}")
async def update(id: PydanticObjectId, product: ProductUpdate):
    updated = await ProductService.update_product(id, product)
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated

@router.delete("/{id}")
async def delete(id: PydanticObjectId):
    success = await ProductService.delete_product(id)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}