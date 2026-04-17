from fastapi import APIRouter, HTTPException, status
from beanie import PydanticObjectId
from typing import List

from app.schemas.category_schema import CategoryResponse, CategoryTreeResponse
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.services.category_services import CategoryService

router = APIRouter()

@router.get("/tree", response_model=ApiResponse[List[CategoryTreeResponse]], response_model_by_alias=False)
async def get_category_tree():
    """
    Public endpoint to fetch the hierarchical category tree.
    """
    tree = await CategoryService.get_category_tree()
    return success_response("Category tree fetched successfully", tree)

@router.get("/", response_model=ApiResponse[List[CategoryResponse]], response_model_by_alias=False)
async def list_categories():
    """
    Public endpoint to fetch all categories as a flat list.
    """
    categories = await CategoryService.get_all_categories()
    return success_response("Categories fetched successfully", categories)

@router.get("/{id}", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False)
async def get_category_by_id(id: PydanticObjectId):
    """
    Public endpoint to fetch specific category details.
    """
    category = await CategoryService.get_category_by_id(id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return success_response("Category fetched successfully", category)