from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId
from typing import List

from app.core.dependencies import RoleChecker, get_current_user
from app.core.user_role import UserRole
from app.models.user_model import User
from app.schemas.category_schema import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryTreeResponse
)
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.services.category_services import CategoryService

router = APIRouter()
manage_category_access = Depends(RoleChecker([UserRole.SUPER_ADMIN, UserRole.ADMIN]))

@router.post("/", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_in: CategoryCreate,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_category_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    created, error = await CategoryService.create_category(category_in, _current_user.id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    return success_response("Category created successfully", created)

# STRICT ORDERING: /tree must be defined before /{id}
@router.get("/tree", response_model=ApiResponse[List[CategoryTreeResponse]], response_model_by_alias=False)
async def get_category_tree():
    tree = await CategoryService.get_category_tree()
    return success_response("Category tree fetched successfully", tree)

@router.get("/", response_model=ApiResponse[List[CategoryResponse]], response_model_by_alias=False)
async def list_categories():
    categories = await CategoryService.get_all_categories()
    return success_response("Categories fetched successfully", categories)

@router.get("/{id}", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False)
async def get_category_by_id(id: PydanticObjectId):
    category = await CategoryService.get_category_by_id(id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return success_response("Category fetched successfully", category)

@router.patch("/{id}", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False)
async def update_category(
    id: PydanticObjectId,
    category_in: CategoryUpdate,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_category_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    updated, error = await CategoryService.update_category(id, category_in, _current_user.id)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    return success_response("Category updated successfully", updated)

@router.delete("/{id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
async def delete_category(
    id: PydanticObjectId,
    _current_user: User = Depends(get_current_user),
    _authorized_user: User = manage_category_access,
):
    if _current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    error = await CategoryService.delete_category(id, _current_user.id)
    if error == "Category not found.":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    return success_response("Category deleted successfully")
