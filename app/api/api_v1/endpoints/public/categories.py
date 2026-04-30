from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from beanie import PydanticObjectId
from typing import List, Optional
from app.core.dependencies import resolve_request_language
from app.core.rate_limiter import ip_key_func, limiter
from app.schemas.category_schema import CategoryResponse, CategoryTreeResponse
from app.schemas.common_schema import ApiResponse
from app.utils.responses import success_response
from app.services.category_services import CategoryService
from app.core.i18n import t
from app.core.message_keys import Msg

router = APIRouter()

@router.get("/tree", response_model=ApiResponse[List[CategoryTreeResponse]], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def get_category_tree(request: Request, language: str = Depends(resolve_request_language)):
    """
    Public endpoint to fetch the hierarchical category tree.
    """
    tree = await CategoryService.get_category_tree(language=language)
    return success_response(
        t(request, Msg.CATEGORY_TREE_FETCHED_SUCCESSFULLY, language=language),
        tree,
    )

@router.get("/", response_model=ApiResponse[List[CategoryResponse]], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def list_categories(
    request: Request,
    search: Optional[str] = Query(default=None, max_length=50, description="Category search term"),
    language: str = Depends(resolve_request_language)
):
    """
    Public endpoint to fetch all categories as a flat list.
    """
    categories = await CategoryService.get_all_categories(
        language=language,
        search=search,
    )
    return success_response(
        t(request, Msg.CATEGORIES_FETCHED_SUCCESSFULLY, language=language),
        categories,
    )

@router.get("/{id}", response_model=ApiResponse[CategoryResponse], response_model_by_alias=False)
@limiter.limit("60/minute", key_func=ip_key_func)
async def get_category_by_id(request: Request, id: PydanticObjectId, language: str = Depends(resolve_request_language)):
    """
    Public endpoint to fetch specific category details.
    """
    category = await CategoryService.get_category_by_id(id, language=language)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t(request, Msg.CATEGORY_NOT_FOUND, language=language))
    return success_response(t(request, Msg.CATEGORY_FETCHED_SUCCESSFULLY, language=language), category)
