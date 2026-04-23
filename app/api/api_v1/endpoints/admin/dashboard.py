from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, status, Request
from app.core.rate_limiter import user_limiter
from app.schemas.dashboard_schema import AdminDashboardSummary, RevenueChartResponse
from app.schemas.common_schema import ApiResponse
from app.services.dashboard_services import DashboardService
from app.utils.responses import success_response

router = APIRouter()

@router.get("/summary", response_model=ApiResponse[AdminDashboardSummary], status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_platform_summary(request: Request):
    """
    Retrieves high-level platform metrics.
    Protected by the Admin gateway boundary.
    """
    data = await DashboardService.get_admin_summary()
    return success_response("Admin dashboard summary fetched successfully", data)

@router.get("/revenue", response_model=ApiResponse[RevenueChartResponse])
@user_limiter.limit("30/minute")    
async def get_admin_revenue(
    request: Request,
    period: Literal["daily", "weekly", "monthly", "yearly"] = "daily",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    try:
        data = await DashboardService.get_revenue_chart(
            period=period, start_date=start_date, end_date=end_date
        )
        return success_response("Admin revenue data fetched", RevenueChartResponse(data=data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))