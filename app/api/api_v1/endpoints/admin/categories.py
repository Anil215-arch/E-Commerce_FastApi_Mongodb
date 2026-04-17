from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.category_schema import CategoryCreate, CategoryUpdate, CategoryResponse
from app.schemas.common_schema import ApiResponse
from app.services.category_services import CategoryService
from app.utils.responses import success_response

router = APIRouter()



@router.post("/", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_category(category_in: CategoryCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    created, error = await CategoryService.create_category(category_in, user_id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    return success_response("Category created successfully", created)

@router.patch("/{id}", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False)
async def update_category(id: PydanticObjectId, category_in: CategoryUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated, error = await CategoryService.update_category(id, category_in, user_id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    return success_response("Category updated successfully", updated)

@router.delete("/{id}", response_model=ApiResponse[None])
async def delete_category(id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    error = await CategoryService.delete_category(id, user_id)
    if error == "Category not found.":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    return success_response("Category deleted successfully")