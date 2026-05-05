from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.dependencies import get_current_user, _require_user_id, RoleChecker
from app.core.i18n import t
from app.core.message_keys import Msg
from app.core.rate_limiter import user_limiter
from app.core.user_role import UserRole
from app.models.user_model import User
from app.schemas.common_schema import ApiResponse
from app.schemas.dashboard_schema import (
    AdminDashboardSummary,
    RevenueChartResponse,
    SellerDashboardSummary,
)
from app.services.dashboard_services import DashboardService
from app.utils.responses import success_response


router = APIRouter()

dashboard_dependency = Depends(
    RoleChecker([UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN])
)

admin_dependency = Depends(
    RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN])
)


@router.get(
    "/seller/summary",
    response_model=ApiResponse[SellerDashboardSummary],
    status_code=status.HTTP_200_OK,
    dependencies=[dashboard_dependency],
)
@user_limiter.limit("30/minute")
async def get_seller_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    seller_id = _require_user_id(current_user)
    data = await DashboardService.get_seller_summary(seller_id)
    return success_response(t(request, Msg.SELLER_DASHBOARD_SUMMARY_FETCHED_SUCCESSFULLY), data)


@router.get(
    "/admin/summary",
    response_model=ApiResponse[AdminDashboardSummary],
    status_code=status.HTTP_200_OK,
    dependencies=[admin_dependency],
)
@user_limiter.limit("30/minute")
async def get_platform_summary(request: Request):
    data = await DashboardService.get_admin_summary()
    return success_response(t(request, Msg.ADMIN_DASHBOARD_SUMMARY_FETCHED_SUCCESSFULLY), data)


@router.get(
    "/revenue",
    response_model=ApiResponse[RevenueChartResponse],
    dependencies=[dashboard_dependency],
)
@user_limiter.limit("30/minute")
async def get_revenue(
    request: Request,
    period: Literal["daily", "weekly", "monthly", "yearly"] = "daily",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
):
    try:
        seller_id = None

        if current_user.role == UserRole.SELLER:
            seller_id = _require_user_id(current_user)

        data = await DashboardService.get_revenue_chart(
            seller_id=seller_id,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )
        message_key = (
            Msg.SELLER_REVENUE_DATA_FETCHED
            if current_user.role == UserRole.SELLER
            else Msg.ADMIN_REVENUE_DATA_FETCHED
        )
        return success_response(t(request, message_key), RevenueChartResponse(data=data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=t(request, str(e)))
