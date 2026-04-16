from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId
from typing import List

from app.core.user_role import UserRole
from app.core.dependencies import get_current_user, RoleChecker
from app.models.user_model import User
from app.schemas.invoice_schema import InvoiceResponse
from app.schemas.order_schema import CheckoutBatchResponse, CheckoutRequest, OrderResponse, OrderUpdateStatusRequest, OrderCancelRequest
from app.schemas.common_schema import ApiResponse
from app.services.invoice_services import InvoiceService
from app.utils.responses import success_response
from app.services.order_services import OrderService
from fastapi import Response
from fastapi.concurrency import run_in_threadpool
from app.services.pdf_services import PDFService

router = APIRouter()

# Role checker for status updates
manage_order_access = Depends(RoleChecker([UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.SELLER]))

@router.post("/checkout", response_model=ApiResponse[CheckoutBatchResponse], response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def process_checkout(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Executes the distributed checkout transaction. 
    Reserves inventory, generates the order, and processes the payment.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
    checkout_batch = await OrderService.checkout(current_user.id, data)
    return success_response("Checkout completed successfully", checkout_batch)


@router.get("/", response_model=ApiResponse[List[OrderResponse]], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_my_orders(
    current_user: User = Depends(get_current_user)
):
    """
    Returns a list of all orders placed by the authenticated user.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    orders = await OrderService.get_my_orders(current_user.id)
    return success_response("Order history fetched successfully", orders)


@router.get("/{order_id}", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_order_by_id(
    order_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    """
    Returns the specific details of a single order. Users can only view their own orders.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    order = await OrderService.get_order_by_id(current_user.id, order_id)
    return success_response("Order details fetched successfully", order)


@router.patch("/{order_id}/status", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def update_order_status(
    order_id: PydanticObjectId,
    data: OrderUpdateStatusRequest,
    current_user: User = Depends(get_current_user),
    _authorized: User = manage_order_access
):
    """
    Updates the fulfillment status of an order. 
    Admins can update any order. Sellers can only update orders containing their products.
    """
    updated_order = await OrderService.update_order_status(order_id, data, current_user)
    return success_response("Order status updated successfully", updated_order)


@router.patch("/{order_id}/cancel", response_model=ApiResponse[OrderResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def cancel_order(
    order_id: PydanticObjectId,
    data: OrderCancelRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Cancels an order, releases reserved inventory back to stock, processes refunds if applicable, 
    and dispatches cancellation notifications.
    """
    # Pass the reason down to the service layer
    cancelled_order = await OrderService.cancel_order(order_id, current_user, data.reason)
    return success_response("Order cancelled and inventory released successfully", cancelled_order)


@router.get("/{order_id}/invoice", response_model=ApiResponse[InvoiceResponse], response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_order_invoice(
    order_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the immutable invoice for a specific order.
    Customers can only retrieve their own invoices.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    invoice = await InvoiceService.get_invoice_by_order_id(order_id, current_user)
    return success_response("Invoice retrieved successfully", invoice)


@router.get(
    "/{order_id}/invoice/pdf", 
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Returns the PDF invoice",
        }
    }
)
async def download_invoice_pdf(
    order_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    """
    Generates and downloads a PDF copy of the order invoice.
    """
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # 1. Fetch the immutable invoice data (reusing your existing logic)
    invoice = await InvoiceService.get_invoice_by_order_id(order_id, current_user)
    
    # 2. Offload the CPU-bound PDF rendering to a background thread
    pdf_bytes = await run_in_threadpool(PDFService.generate_invoice_pdf, invoice)
    
    # 3. Return the raw bytes as a downloadable file
    headers = {
        "Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)