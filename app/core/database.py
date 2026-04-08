from beanie import init_beanie
from app.core.config import settings
from app.models.product_model import Product
from app.models.category_model import Category
from app.models.revoked_token_model import RevokedToken
from app.models.user_model import User

async def init_db():
    await init_beanie(
        connection_string=f"{settings.MONGODB_URL}/{settings.DATABASE_NAME}",
        document_models=[Product, Category, User, RevokedToken],
    )
