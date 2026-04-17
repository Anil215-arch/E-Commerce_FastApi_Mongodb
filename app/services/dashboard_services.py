import asyncio

from beanie import PydanticObjectId
from app.models.user_model import User
from app.models.order_model import Order
from app.models.product_model import Product
from app.models.category_model import Category
from app.core.user_role import UserRole
from app.schemas.dashboard_schema import AdminDashboardSummary, SellerDashboardSummary, SellerDashboardSummary

class DashboardService:
    @classmethod
    async def get_admin_summary(cls) -> AdminDashboardSummary:
        """
        Executes parallel count queries across core collections.
        """
        results = await asyncio.gather(
            User.find_all().count(),
            User.find({"role": UserRole.SELLER}).count(),
            Order.find_all().count(),
            Product.find_all().count(),
            Category.find_all().count()
        )
        
        # Unpack the results in the exact order they were awaited
        total_users, total_sellers, total_orders, total_products, total_categories = results
        
        return AdminDashboardSummary(
            total_users=total_users,
            total_sellers=total_sellers,
            total_orders=total_orders,
            total_products=total_products,
            total_categories=total_categories
        )
    
    @classmethod
    async def get_seller_summary(cls, seller_id: PydanticObjectId) -> SellerDashboardSummary:
        """
        Executes parallel count queries strictly scoped to the seller's ID.
        """
        results = await asyncio.gather(
            Product.find({"seller_id": seller_id}).count(),
            Order.find({"items.seller_id": seller_id}).count()
        )
        
        total_products, total_orders = results
        
        return SellerDashboardSummary(
            total_products=total_products,
            total_orders=total_orders
        )