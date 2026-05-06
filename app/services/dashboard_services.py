import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional
from beanie import PydanticObjectId

from app.models.user_model import User
from app.models.order_model import Order, OrderPaymentStatus, OrderStatus
from app.models.product_model import Product
from app.models.category_model import Category
from app.core.user_role import UserRole
from app.core.message_keys import Msg
from app.schemas.dashboard_schema import (
    AdminDashboardSummary, 
    SellerDashboardSummary, 
    DailyRevenue
)

class DashboardService:
    @classmethod
    def _zero_fill(
        cls,
        results: list[DailyRevenue],
        start_date: datetime,
        end_date: datetime,
        period: str
    ) -> list[DailyRevenue]:
        revenue_map = {r.date: r.revenue for r in results}
        filled: list[DailyRevenue] = []
        current = start_date

        while current <= end_date:
            if period == "daily":
                key = current.strftime("%Y-%m-%d")
                current += timedelta(days=1)
            elif period == "weekly":
                key = current.strftime("%G-W%V")
                current += timedelta(weeks=1)
            elif period == "monthly":
                key = current.strftime("%Y-%m")
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    current = current.replace(month=current.month + 1, day=1)
            elif period == "yearly":
                key = current.strftime("%Y")
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                raise ValueError(Msg.INVALID_REVENUE_PERIOD)

            filled.append(DailyRevenue(date=key, revenue=revenue_map.get(key, 0)))
        
        filled.sort(key=lambda x: x.date)
        return filled

    @classmethod
    async def get_admin_summary(cls) -> AdminDashboardSummary:
        results = await asyncio.gather(
            User.find_all().count(),
            User.find({"role": UserRole.SELLER}).count(),
            Order.find_all().count(),
            Product.find_all().count(),
            Category.find_all().count()
        )
        return AdminDashboardSummary(
            total_users=results[0], total_sellers=results[1],
            total_orders=results[2], total_products=results[3],
            total_categories=results[4]
        )

    @classmethod
    async def get_seller_summary(cls, seller_id: PydanticObjectId) -> SellerDashboardSummary:
        results = await asyncio.gather(
            Product.find({"seller_id": seller_id}).count(),
            Order.find({"seller_id": seller_id}).count()
        )
        return SellerDashboardSummary(total_products=results[0], total_orders=results[1])

    @classmethod
    async def get_revenue_chart(
        cls, 
        seller_id: Optional[PydanticObjectId] = None, 
        period: str = "daily",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> list[DailyRevenue]:
        # 1. Timezone Discipline & Guardrails
        now = datetime.now(timezone.utc)
        
        if start_date and end_date and (end_date - start_date).days > 1825:
            raise ValueError(Msg.DATE_RANGE_EXCEEDS_FIVE_YEAR_LIMIT)

        if not start_date:
            lookback = {"daily": 30, "weekly": 60, "monthly": 365, "yearly": 1825}
            start_date = now - timedelta(days=lookback.get(period, 30))
        
        # Alignment
        if period == "weekly": start_date -= timedelta(days=start_date.weekday())
        elif period == "monthly": start_date = start_date.replace(day=1)
        elif period == "yearly": start_date = start_date.replace(month=1, day=1)
        
        end_date = end_date or now

        # 2. Aggregation
        match_filter: dict[str, Any] = {
            "created_at": {"$gte": start_date, "$lte": end_date},
            "payment_status": OrderPaymentStatus.PAID.value,
            "status": {"$ne": OrderStatus.CANCELLED.value}
        }
        if seller_id:
            match_filter["seller_id"] = seller_id

        formats = {"daily": "%Y-%m-%d", "weekly": "%G-W%V", "monthly": "%Y-%m", "yearly": "%Y"}
        
        pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": {"$dateToString": {"format": formats[period], "date": "$created_at"}},
                "revenue": {"$sum": "$grand_total"}
            }},
            {"$sort": {"_id": 1}}
        ]

        results = await Order.aggregate(pipeline).to_list()
        
        # 3. Revenue stays in paisa (int) to avoid floating-point precision drift.
        data = [DailyRevenue(date=r["_id"], revenue=int(r["revenue"])) for r in results]
        return cls._zero_fill(data, start_date, end_date, period)