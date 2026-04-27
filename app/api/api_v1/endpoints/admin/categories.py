from fastapi import APIRouter, Depends, HTTPException, status, Request
from beanie import PydanticObjectId
from app.core.message_keys import Msg
from app.core.i18n import t
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.category_schema import CategoryCreate, CategoryManageResponse, CategoryUpdate
from app.schemas.common_schema import ApiResponse
from app.services.category_services import CategoryService
from app.utils.responses import success_response

router = APIRouter()



@router.post("/", response_model=ApiResponse[CategoryManageResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
@user_limiter.limit("10/minute")
async def create_category(request: Request, category_in: CategoryCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    created, error = await CategoryService.create_category(category_in, user_id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t(request, error))
    return success_response(t(request, Msg.CATEGORY_CREATED_SUCCESSFULLY), created)

@router.patch("/{id}", response_model=ApiResponse[CategoryManageResponse], response_model_by_alias=False)
@user_limiter.limit("10/minute")
async def update_category(request: Request, id: PydanticObjectId, category_in: CategoryUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated, error = await CategoryService.update_category(id, category_in, user_id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t(request, error))
    return success_response(t(request, Msg.CATEGORY_UPDATED_SUCCESSFULLY), updated)

@router.delete("/{id}", response_model=ApiResponse[None])
@user_limiter.limit("10/minute")
async def delete_category(request: Request, id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    error = await CategoryService.delete_category(id, user_id)
    if error == "Category not found.":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.CATEGORY_NOT_FOUND))
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t(request, error))
    return success_response(t(request, Msg.CATEGORY_DELETED_SUCCESSFULLY))