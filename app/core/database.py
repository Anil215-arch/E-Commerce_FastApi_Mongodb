from beanie import init_beanie
from app.core.config import settings
from app.models.product_model import Product  

async def init_db():
    await init_beanie(
        connection_string=f"{settings.MONGODB_URL}/{settings.DATABASE_NAME}",
        document_models=[Product],
    )