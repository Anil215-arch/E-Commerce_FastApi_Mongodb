from pydantic import BaseModel, Field
from typing import List

class AdminDashboardSummary(BaseModel):
    total_users: int = Field(..., ge=0)
    total_sellers: int = Field(..., ge=0)
    total_orders: int = Field(..., ge=0)
    total_products: int = Field(..., ge=0)
    total_categories: int = Field(..., ge=0)
    
    
class SellerDashboardSummary(BaseModel):
    total_products: int = Field(..., ge=0)
    total_orders: int = Field(..., ge=0)

class DailyRevenue(BaseModel):
    date: str
    revenue: int = Field(..., ge=0)

class RevenueChartResponse(BaseModel):
    data: List[DailyRevenue]