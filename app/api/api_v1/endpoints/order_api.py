from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
from fastapi.concurrency import run_in_threadpool
from beanie import PydanticObjectId
from typing import List
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user, _require_user_id, RoleChecker
from app.core.user_role import UserRole
from app.models.user_model import User
from app.schemas.invoice_schema import InvoiceResponse
from app.schemas.order_schema import (
    CheckoutBatchResponse, CheckoutRequest, OrderResponse, OrderCancelRequest,
    OrderUpdateStatusRequest
)
from app.schemas.common_schema import ApiResponse
from app.services.invoice_services import InvoiceService
from app.services.order_services import OrderService
from app.services.pdf_services import PDFService
from app.utils.responses import success_response

router = APIRouter()
seller_router = APIRouter(
    prefix="/seller",
    dependencies=[Depends(RoleChecker([UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)


@router.post("/checkout", response_model=ApiResponse[CheckoutBatchResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
@user_limiter.limit("5/minute")
async def process_checkout(request: Request, data: CheckoutRequest, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    checkout_batch = await OrderService.checkout(user_id, data)
    return success_response("Checkout completed successfully", checkout_batch)


@router.get("/", response_model=ApiResponse[List[OrderResponse]], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_my_orders(request: Request, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    orders = await OrderService.get_my_orders(user_id)
    return success_response("Order history fetched successfully", orders)


@router.get("/{order_id}", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_order_by_id(request: Request, order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    order = await OrderService.get_order_by_id(user_id, order_id)
    return success_response("Order details fetched successfully", order)


@router.patch("/{order_id}/cancel", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def cancel_order(request: Request, order_id: PydanticObjectId, data: OrderCancelRequest, current_user: User = Depends(get_current_user)):
    cancelled_order = await OrderService.cancel_order(order_id, current_user, data.reason)
    return success_response("Order cancelled and inventory released successfully", cancelled_order)


@router.get("/{order_id}/invoice", response_model=ApiResponse[InvoiceResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("20/minute")
async def get_order_invoice(request: Request, order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    _require_user_id(current_user)
    invoice = await InvoiceService.get_invoice_by_order_id(order_id, current_user)
    return success_response("Invoice retrieved successfully", invoice)


@router.get("/{order_id}/invoice/pdf", response_class=Response)
@user_limiter.limit("10/minute")
async def download_invoice_pdf(request: Request, order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    _require_user_id(current_user)
    invoice = await InvoiceService.get_invoice_by_order_id(order_id, current_user)
    pdf_bytes = await run_in_threadpool(PDFService.generate_invoice_pdf, invoice)
    headers = {"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@seller_router.patch("/{order_id}/status", response_model=ApiResponse[OrderResponse])
@user_limiter.limit("10/minute")
async def update_seller_order_status(request: Request, order_id: PydanticObjectId, data: OrderUpdateStatusRequest, current_user: User = Depends(get_current_user)):
    """
    Seller endpoint to update fulfillment status.
    The Service layer must ensure the seller owns the products in this order.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user id is missing")

    updated_order = await OrderService.update_order_status(order_id, data, current_user)
    return success_response("Order status updated successfully", updated_order)


@admin_router.patch("/{order_id}/status", response_model=ApiResponse[OrderResponse], status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def update_order_status_as_admin(request: Request, order_id: PydanticObjectId, data: OrderUpdateStatusRequest, current_user: User = Depends(get_current_user)):
    """
    Admin Intervention: Override fulfillment status for any order.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user id is missing")

    updated_order = await OrderService.update_order_status(order_id, data, current_user)
    return success_response("Order status updated successfully by Admin", updated_order)


@admin_router.patch("/{order_id}/cancel", response_model=ApiResponse[OrderResponse], status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def cancel_order_as_admin(request: Request, order_id: PydanticObjectId, data: OrderCancelRequest, current_user: User = Depends(get_current_user)):
    """
    Admin Intervention: Force cancel any order and process refunds.
    """
    cancelled_order = await OrderService.cancel_order(order_id, current_user, data.reason)
    return success_response("Order cancelled successfully by Admin", cancelled_order)


router.include_router(seller_router)
router.include_router(admin_router)
