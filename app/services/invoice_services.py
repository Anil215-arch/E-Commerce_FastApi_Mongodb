from app.models.order_model import Order
from app.models.invoice_model import Invoice
from app.models.transaction_model import Transaction
from app.schemas.invoice_schema import InvoiceResponse
from app.models.user_model import User
from app.models.product_model import Product
from app.models.order_model import OrderItemSnapshot
from app.utils.product_mapper import ProductMapper
from app.core.user_role import UserRole
from fastapi import HTTPException, status
from beanie import PydanticObjectId
from app.services.sequence_services import SequenceService
from app.validators.invoice_validator import InvoiceDomainValidator
from app.core.message_keys import Msg

class InvoiceService:
    
    @staticmethod
    async def _build_localized_invoice_response(
        invoice: Invoice,
        language: str | None = None,
    ) -> InvoiceResponse:
        if not language:
            return InvoiceResponse.model_validate(invoice)

        product_ids = list({item.product_id for item in invoice.items})
        products = await Product.find({
            "_id": {"$in": product_ids},
            "is_deleted": {"$ne": True},
        }).to_list()

        product_map = {str(product.id): product for product in products}

        localized_items = []
        for item in invoice.items:
            item_data = item.model_dump()
            product = product_map.get(str(item.product_id))

            if product:
                localized_name, _ = ProductMapper._localized_product_content(product, language)
                item_data["product_name"] = localized_name

            localized_items.append(OrderItemSnapshot(**item_data))

        invoice_data = invoice.model_dump()
        invoice_data["items"] = localized_items
        return InvoiceResponse.model_validate(invoice_data)
    
    @staticmethod
    async def create_invoice_from_order(order: Order, transaction: Transaction) -> Invoice:
        # 1. Idempotency Check
        existing_invoice = await Invoice.find_one(Invoice.order_id == order.id)
        if existing_invoice:
            return existing_invoice

        # 2. Generate Atomic Sequence
        invoice_number = await SequenceService.next_invoice_number()
        InvoiceDomainValidator.validate_items(order.items)
        InvoiceDomainValidator.validate_financial_math(
            subtotal=order.subtotal,
            tax=order.tax_amount,
            shipping=order.shipping_fee,
            grand_total=order.grand_total
        )
        InvoiceDomainValidator.validate_transaction_coverage(
            invoice_total=order.grand_total,
            transaction_amount=transaction.amount
        )
        # 3. Snapshot and Save
        invoice = Invoice(
            invoice_number=invoice_number,
            order_id=order.id, # type: ignore
            transaction_id=order.transaction_id,
            user_id=order.user_id,
            items=order.items,
            shipping_address=order.shipping_address,
            billing_address=order.billing_address,
            subtotal=order.subtotal,
            tax_amount=order.tax_amount,
            shipping_fee=order.shipping_fee,
            grand_total=order.grand_total,
            currency="INR",
            payment_method=transaction.payment_method,
            gateway_transaction_id=transaction.gateway_transaction_id,
            created_by=order.user_id
        )
        await invoice.insert()
        return invoice
    
    @staticmethod
    async def get_invoice_by_order_id(order_id: PydanticObjectId, current_user: User, language: str | None = None,) -> InvoiceResponse:
        invoice = await Invoice.find_one({"order_id": order_id})
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=Msg.INVOICE_NOT_FOUND_FOR_ORDER
            )

        # Authorization: Only the buyer or an Admin can view the invoice
        if current_user.role == UserRole.CUSTOMER and invoice.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=Msg.NO_PERMISSION_VIEW_INVOICE
            )

        return await InvoiceService._build_localized_invoice_response(invoice, language=language)