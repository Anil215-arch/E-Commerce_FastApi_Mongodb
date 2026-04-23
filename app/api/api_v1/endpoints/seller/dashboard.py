from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Depends,HTTPException, status, Request
from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.dashboard_schema import RevenueChartResponse, SellerDashboardSummary
from app.schemas.common_schema import ApiResponse
from app.services.dashboard_services import DashboardService
from app.utils.responses import success_response
from app.core.rate_limiter import user_limiter

router = APIRouter()


@router.get("/summary", response_model=ApiResponse[SellerDashboardSummary], status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_seller_summary(request: Request, current_user: User = Depends(get_current_user)):
    """
    Retrieves isolated platform metrics for the authenticated seller.
    """
    seller_id = _require_user_id(current_user)
    data = await DashboardService.get_seller_summary(seller_id)
    return success_response("Seller dashboard summary fetched successfully", data)

@router.get("/revenue", response_model=ApiResponse[RevenueChartResponse])
@user_limiter.limit("30/minute")    
async def get_seller_revenue(
    request: Request,
    period: Literal["daily", "weekly", "monthly", "yearly"] = "daily",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user)
):
    try:
        seller_id = _require_user_id(current_user)
        data = await DashboardService.get_revenue_chart(
            seller_id=seller_id, period=period, start_date=start_date, end_date=end_date
        )
        return success_response("Seller revenue data fetched", RevenueChartResponse(data=data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))