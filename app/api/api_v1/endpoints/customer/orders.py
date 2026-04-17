from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.concurrency import run_in_threadpool
from beanie import PydanticObjectId
from typing import List

from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.invoice_schema import InvoiceResponse
from app.schemas.order_schema import CheckoutBatchResponse, CheckoutRequest, OrderResponse, OrderCancelRequest
from app.schemas.common_schema import ApiResponse
from app.services.invoice_services import InvoiceService
from app.services.order_services import OrderService
from app.services.pdf_services import PDFService
from app.utils.responses import success_response

router = APIRouter()


@router.post("/checkout", response_model=ApiResponse[CheckoutBatchResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def process_checkout(data: CheckoutRequest, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    checkout_batch = await OrderService.checkout(user_id, data)
    return success_response("Checkout completed successfully", checkout_batch)

@router.get("/", response_model=ApiResponse[List[OrderResponse]], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_my_orders(current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    orders = await OrderService.get_my_orders(user_id)
    return success_response("Order history fetched successfully", orders)

@router.get("/{order_id}", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_order_by_id(order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    order = await OrderService.get_order_by_id(user_id, order_id)
    return success_response("Order details fetched successfully", order)

@router.patch("/{order_id}/cancel", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def cancel_order(order_id: PydanticObjectId, data: OrderCancelRequest, current_user: User = Depends(get_current_user)):
    cancelled_order = await OrderService.cancel_order(order_id, current_user, data.reason)
    return success_response("Order cancelled and inventory released successfully", cancelled_order)

@router.get("/{order_id}/invoice", response_model=ApiResponse[InvoiceResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_order_invoice(order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    _require_user_id(current_user)
    invoice = await InvoiceService.get_invoice_by_order_id(order_id, current_user)
    return success_response("Invoice retrieved successfully", invoice)

@router.get("/{order_id}/invoice/pdf", response_class=Response)
async def download_invoice_pdf(order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    _require_user_id(current_user)
    invoice = await InvoiceService.get_invoice_by_order_id(order_id, current_user)
    pdf_bytes = await run_in_threadpool(PDFService.generate_invoice_pdf, invoice)
    headers = {"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)