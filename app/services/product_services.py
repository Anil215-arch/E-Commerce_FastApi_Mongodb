from app.models.product_model import Product
from app.schemas.product_schema import ProductCreate, ProductUpdate
from beanie import PydanticObjectId

class ProductService:
    @staticmethod
    async def create_product(data: ProductCreate) -> Product:
        new_product = Product(**data.model_dump())
        return await new_product.insert()

    @staticmethod
    async def get_all_products():
        return await Product.find_all().to_list()

    @staticmethod
    async def get_product(id: PydanticObjectId):
        return await Product.get(id)

    @staticmethod
    async def update_product(id: PydanticObjectId, data: ProductUpdate):
        product = await Product.get(id)
        if product:
            update_query = {"$set": data.model_dump(exclude_unset=True)}
            await product.update(update_query)
            return product
        return None

    @staticmethod
    async def delete_product(id: PydanticObjectId):
        product = await Product.get(id)
        if product:
            await product.delete()
            return True
        return False