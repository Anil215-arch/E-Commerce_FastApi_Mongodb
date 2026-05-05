from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from beanie import PydanticObjectId
from typing import List, Optional

from app.core.i18n import t
from app.core.message_keys import Msg
from app.core.dependencies import get_current_user, _require_user_id, resolve_request_language, RoleChecker
from app.core.rate_limiter import ip_key_func, limiter, user_limiter
from app.core.user_role import UserRole
from app.models.user_model import User
from app.schemas.category_schema import (
    CategoryCreate, CategoryUpdate, CategoryResponse, CategoryTreeResponse
)
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.services.category_services import CategoryService

router = APIRouter()
admin_dependency = Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))


@router.get("/tree", response_model=ApiResponse[List[CategoryTreeResponse]], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def get_category_tree(
    request: Request,
    language: str = Depends(resolve_request_language),
):
    """
    Public endpoint to fetch the hierarchical category tree.
    """
    tree = await CategoryService.get_category_tree(language=language)
    return success_response(t(request, Msg.CATEGORY_TREE_FETCHED_SUCCESSFULLY, language=language), tree)


@router.get("", response_model=ApiResponse[List[CategoryResponse]], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def list_categories(
    request: Request,
    search: Optional[str] = Query(default=None, max_length=50, description="Category search term"),
    language: str = Depends(resolve_request_language),
):
    """
    Public endpoint to fetch all categories as a flat list.
    """
    categories = await CategoryService.get_all_categories(language=language, search=search)
    return success_response(t(request, Msg.CATEGORIES_FETCHED_SUCCESSFULLY, language=language), categories)


@router.get("/{id}", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def get_category_by_id(
    request: Request,
    id: PydanticObjectId,
    language: str = Depends(resolve_request_language),
):
    """
    Public endpoint to fetch specific category details.
    """
    category = await CategoryService.get_category_by_id(id, language=language)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=Msg.CATEGORY_NOT_FOUND)
    return success_response(t(request, Msg.CATEGORY_FETCHED_SUCCESSFULLY, language=language), category)


@router.post("", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED, dependencies=[admin_dependency])
@user_limiter.limit("10/minute")
async def create_category(request: Request, category_in: CategoryCreate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    created, error = await CategoryService.create_category(category_in, user_id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t(request, error))
    return success_response(t(request, Msg.CATEGORY_CREATED_SUCCESSFULLY), created)


@router.patch("/{id}", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False, dependencies=[admin_dependency])
@user_limiter.limit("10/minute")
async def update_category(request: Request, id: PydanticObjectId, category_in: CategoryUpdate, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    updated, error = await CategoryService.update_category(id, category_in, user_id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t(request, error))
    return success_response(t(request, Msg.CATEGORY_UPDATED_SUCCESSFULLY), updated)


@router.delete("/{id}", response_model=ApiResponse[None], dependencies=[admin_dependency])
@user_limiter.limit("10/minute")
async def delete_category(request: Request, id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    error = await CategoryService.delete_category(id, user_id)
    if error == Msg.CATEGORY_NOT_FOUND:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, error))
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t(request, error))
    return success_response(t(request, Msg.CATEGORY_DELETED_SUCCESSFULLY))
