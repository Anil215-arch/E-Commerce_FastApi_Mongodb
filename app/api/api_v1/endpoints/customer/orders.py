from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
from fastapi.concurrency import run_in_threadpool
from beanie import PydanticObjectId
from typing import List
from app.core.rate_limiter import user_limiter
from app.core.dependencies import get_current_user, _require_user_id
from app.models.user_model import User
from app.schemas.invoice_schema import InvoiceResponse
from app.schemas.order_schema import CheckoutBatchResponse, CheckoutRequest, OrderResponse, OrderCancelRequest
from app.schemas.common_schema import ApiResponse
from app.services.invoice_services import InvoiceService
from app.services.order_services import OrderService
from app.services.pdf_services import PDFService
from app.utils.responses import success_response
from app.core.i18n import get_language, t
from app.core.message_keys import Msg

router = APIRouter()

def _user_language(current_user: User, request: Request) -> str:
    return getattr(current_user, "preferred_language", None) or get_language(request)

@router.post("/checkout", response_model=ApiResponse[CheckoutBatchResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
@user_limiter.limit("5/minute")
async def process_checkout(request: Request, data: CheckoutRequest, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    language = _user_language(current_user, request)
    checkout_batch = await OrderService.checkout(
        user_id,
        data,
        language=language,
    )
    return success_response(
        t(request, Msg.CHECKOUT_COMPLETED_SUCCESSFULLY, language=language),
        checkout_batch,
    )

@router.get("/", response_model=ApiResponse[List[OrderResponse]], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_my_orders(request: Request, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    language = _user_language(current_user, request)
    orders = await OrderService.get_my_orders(user_id, language=language)
    return success_response(
        t(request, Msg.ORDER_HISTORY_FETCHED_SUCCESSFULLY, language=language),
        orders,
    )

@router.get("/{order_id}", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("30/minute")
async def get_order_by_id(request: Request, order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    user_id = _require_user_id(current_user)
    language = _user_language(current_user, request)
    order = await OrderService.get_order_by_id(user_id, order_id, language=language)
    return success_response(
        t(request, Msg.ORDER_DETAILS_FETCHED_SUCCESSFULLY, language=language),
        order,
    )

@router.patch("/{order_id}/cancel", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("10/minute")
async def cancel_order(request: Request, order_id: PydanticObjectId, data: OrderCancelRequest, current_user: User = Depends(get_current_user)):
    language = _user_language(current_user, request)
    cancelled_order = await OrderService.cancel_order(
        order_id,
        current_user,
        data.reason,
        language=language,
    )
    return success_response(
        t(request, Msg.ORDER_CANCELLED_INVENTORY_RELEASED_SUCCESSFULLY, language=language),
        cancelled_order,
    )

@router.get("/{order_id}/invoice", response_model=ApiResponse[InvoiceResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
@user_limiter.limit("20/minute")
async def get_order_invoice(request: Request, order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    _require_user_id(current_user)
    language = _user_language(current_user, request)
    invoice = await InvoiceService.get_invoice_by_order_id(order_id, current_user, language=language)
    return success_response(t(request, Msg.INVOICE_RETRIEVED_SUCCESSFULLY, language=language), invoice)

@router.get("/{order_id}/invoice/pdf", response_class=Response)
@user_limiter.limit("10/minute")
async def download_invoice_pdf(request: Request, order_id: PydanticObjectId, current_user: User = Depends(get_current_user)):
    _require_user_id(current_user)
    invoice = await InvoiceService.get_invoice_by_order_id(order_id, current_user)
    pdf_bytes = await run_in_threadpool(PDFService.generate_invoice_pdf, invoice)
    headers = {"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
