from fastapi import APIRouter, Depends, HTTPException, status, Request
from beanie import PydanticObjectId
from app.core.rate_limiter import user_limiter
from app.core.dependencies import _require_user_id, get_current_user
from app.models.user_model import User
from app.schemas.common_schema import ApiResponse
from app.services.product_services import ProductService
from app.utils.responses import success_response

router = APIRouter()

@router.delete("/{id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def delete_product_as_admin(request: Request, id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    """
    Admin Moderation: Force delete any product from the platform.
    """
    user_id = _require_user_id(current_user)
    success = await ProductService.delete_product(id, user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return success_response("Product deleted successfully by Admin")