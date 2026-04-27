from fastapi import APIRouter, HTTPException, Request, status
from beanie import PydanticObjectId
from typing import List

from app.core.rate_limiter import ip_key_func, limiter
from app.schemas.category_schema import CategoryResponse, CategoryTreeResponse
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.services.category_services import CategoryService
from app.core.i18n import get_language, t
from app.core.message_keys import Msg

router = APIRouter()

@router.get("/tree", response_model=ApiResponse[List[CategoryTreeResponse]], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def get_category_tree(request: Request):
    """
    Public endpoint to fetch the hierarchical category tree.
    """
    tree = await CategoryService.get_category_tree(language=get_language(request))
    return success_response(t(request, Msg.CATEGORY_TREE_FETCHED_SUCCESSFULLY), tree)

@router.get("/", response_model=ApiResponse[List[CategoryResponse]], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def list_categories(request: Request):
    """
    Public endpoint to fetch all categories as a flat list.
    """
    categories = await CategoryService.get_all_categories(language=get_language(request))
    return success_response(t(request, Msg.CATEGORIES_FETCHED_SUCCESSFULLY), categories)

@router.get("/{id}", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def get_category_by_id(request: Request, id: PydanticObjectId):
    """
    Public endpoint to fetch specific category details.
    """
    category = await CategoryService.get_category_by_id(id, language=get_language(request))
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.CATEGORY_NOT_FOUND))
    return success_response(t(request, Msg.CATEGORY_FETCHED_SUCCESSFULLY), category)
