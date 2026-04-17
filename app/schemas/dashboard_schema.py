from pydantic import BaseModel

class AdminDashboardSummary(BaseModel):
    total_users: int
    total_sellers: int
    total_orders: int
    total_products: int
    total_categories: int
    
    
class SellerDashboardSummary(BaseModel):
    total_products: int
    total_orders: int