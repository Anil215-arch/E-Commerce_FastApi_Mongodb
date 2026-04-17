from fastapi import APIRouter, status

from app.schemas.dashboard_schema import AdminDashboardSummary
from app.schemas.common_schema import ApiResponse
from app.services.dashboard_services import DashboardService
from app.utils.responses import success_response

router = APIRouter()

@router.get("/summary", response_model=ApiResponse[AdminDashboardSummary], status_code=status.HTTP_200_OK)
async def get_platform_summary():
    """
    Retrieves high-level platform metrics.
    Protected by the Admin gateway boundary.
    """
    data = await DashboardService.get_admin_summary()
    return success_response("Admin dashboard summary fetched successfully", data)