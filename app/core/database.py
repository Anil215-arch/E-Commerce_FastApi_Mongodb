from beanie import init_beanie
from app.core.config import settings
from app.models.cart_model import Cart
from app.models.email_otp_model import EmailOTPVerification
from app.models.order_model import Order
from app.models.product_model import Product
from app.models.category_model import Category
from app.models.revoked_token_model import RevokedToken
from app.models.transaction_model import Transaction
from app.models.user_model import User
from app.models.invoice_model import Invoice
from app.models.counter_model import Counter


async def init_db():
    await init_beanie(
        connection_string=f"{settings.MONGODB_URL}/{settings.DATABASE_NAME}",
        document_models=[ 
            Product, 
            Category, 
            User, 
            RevokedToken, 
            Cart, 
            EmailOTPVerification,
            Order,
            Transaction,
            Invoice,
            Counter
        ],
    )
    