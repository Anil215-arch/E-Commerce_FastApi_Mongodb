from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.dependencies import get_current_user, _require_user_id, RoleChecker
from app.core.user_role import UserRole
from app.models.user_model import User
from app.schemas.dashboard_schema import (
    RevenueChartResponse, SellerDashboardSummary, AdminDashboardSummary
)
from app.schemas.common_schema import ApiResponse
from app.services.dashboard_services import DashboardService
from app.utils.responses import success_response
from app.core.rate_limiter import user_limiter

router = APIRouter()
seller_router = APIRouter(
    prefix="/seller",
    dependencies=[Depends(RoleChecker([UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)


@seller_router.get("/summary", response_model=ApiResponse[SellerDashboardSummary], status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_seller_summary(request: Request, current_user: User = Depends(get_current_user)):
    """
    Retrieves isolated platform metrics for the authenticated seller.
    """
    seller_id = _require_user_id(current_user)
    data = await DashboardService.get_seller_summary(seller_id)
    return success_response("Seller dashboard summary fetched successfully", data)


@seller_router.get("/revenue", response_model=ApiResponse[RevenueChartResponse])
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


@admin_router.get("/summary", response_model=ApiResponse[AdminDashboardSummary], status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_platform_summary(request: Request):
    """
    Retrieves high-level platform metrics.
    Protected by the Admin gateway boundary.
    """
    data = await DashboardService.get_admin_summary()
    return success_response("Admin dashboard summary fetched successfully", data)


@admin_router.get("/revenue", response_model=ApiResponse[RevenueChartResponse])
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


router.include_router(seller_router)
router.include_router(admin_router)
