from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.dashboard_schema import SellerDashboardSummary
from app.schemas.common_schema import ApiResponse
from app.services.dashboard_services import DashboardService
from app.utils.responses import success_response

router = APIRouter()


@router.get("/summary", response_model=ApiResponse[SellerDashboardSummary], status_code=status.HTTP_200_OK)
async def get_seller_summary(current_user: User = Depends(get_current_user)):
    """
    Retrieves isolated platform metrics for the authenticated seller.
    """
    seller_id = _require_user_id(current_user)
    data = await DashboardService.get_seller_summary(seller_id)
    return success_response("Seller dashboard summary fetched successfully", data)