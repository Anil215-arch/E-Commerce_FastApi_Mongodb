from datetime import datetime, timezone

from beanie import PydanticObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.models.inventory_ledger_model import InventoryLedger
from app.models.product_model import Product
from app.models.product_variant_model import ProductVariant
from app.schemas.inventory_schema import InventoryVariantResponse
from app.validators.inventory_validator import InventoryDomainValidator
from app.core.message_keys import Msg

class InventoryService:

    @staticmethod
    async def _get_variant_or_raise(
        product_id: PydanticObjectId,
        sku: str,
        seller_id: PydanticObjectId,
    ) -> ProductVariant:
        query: dict = {
            "_id": product_id,
            "is_deleted": {"$ne": True},
            "created_by": seller_id,
        }
        product = await Product.find_one(query)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=Msg.PRODUCT_NOT_FOUND,
            )

        variant = next((item for item in product.variants if item.sku == sku), None)
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=Msg.VARIANT_NOT_FOUND,
            )
        return variant

    @staticmethod
    async def get_variant_inventory(
        product_id: PydanticObjectId,
        sku: str,
        seller_id: PydanticObjectId,
    ) -> InventoryVariantResponse:
        variant = await InventoryService._get_variant_or_raise(product_id, sku, seller_id)
        return InventoryVariantResponse(
            product_id=product_id,
            sku=sku,
            available_stock=variant.available_stock,
            reserved_stock=variant.reserved_stock,
            total_stock=variant.available_stock + variant.reserved_stock,
        )

    @staticmethod
    async def adjust_available_stock(
        product_id: PydanticObjectId,
        sku: str,
        owner_seller_id: PydanticObjectId,
        actor_user_id: PydanticObjectId,
        request_id: str,
        delta: int,
        reason: str,
    ) -> InventoryVariantResponse:
        
        InventoryDomainValidator.validate_request_id(request_id)
        InventoryDomainValidator.validate_reason(reason)
        InventoryDomainValidator.validate_sku(sku)
        collection = Product.get_pymongo_collection()  # type: ignore
        ledger_collection = InventoryLedger.get_pymongo_collection()  # type: ignore

        update_filter: dict = {
            "_id": product_id,
            "is_deleted": {"$ne": True},
            "created_by": owner_seller_id,
            "variants": {"$elemMatch": {"sku": sku}},
        }
        if delta < 0:
            update_filter = {
                "_id": product_id,
                "is_deleted": {"$ne": True},
                "created_by": owner_seller_id,
                "variants": {
                    "$elemMatch": {
                        "sku": sku,
                        "available_stock": {"$gte": abs(delta)},
                    }
                },
            }

        try:
            async with collection.database.client.start_session() as session:
                async def _run_transactional_mutation() -> None:
                    previous_product = await collection.find_one_and_update(
                        update_filter,
                        {"$inc": {"variants.$.available_stock": delta}},
                        projection={"variants.$": 1},
                        return_document=ReturnDocument.BEFORE,
                        session=session,
                    )

                    if not previous_product:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=Msg.INVENTORY_UPDATE_FAILED,
                        )

                    previous_variant = (previous_product.get("variants") or [None])[0]
                    if not previous_variant:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=Msg.INVENTORY_SKU_SNAPSHOT_UNAVAILABLE,
                        )

                    previous_stock = int(previous_variant.get("available_stock", 0))
                    new_stock = previous_stock + delta
                    if new_stock < 0:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=Msg.INVENTORY_NEGATIVE_STOCK,
                        )
                    InventoryDomainValidator.validate_stock_ceiling(new_stock)
                    now = datetime.now(timezone.utc)
                    await ledger_collection.insert_one(
                        {
                            "product_id": product_id,
                            "sku": sku,
                            "user_id": actor_user_id,
                            "actor_user_id": actor_user_id,
                            "owner_seller_id": owner_seller_id,
                            "request_id": request_id,
                            "delta": delta,
                            "previous_stock": previous_stock,
                            "new_stock": new_stock,
                            "reason": reason,
                            "created_at": now,
                            "updated_at": now,
                            "is_deleted": False,
                            "created_by": actor_user_id,
                            "updated_by": actor_user_id,
                        },
                        session=session,
                    )

                transaction_ctx = await session.start_transaction()
                async with transaction_ctx:
                    await _run_transactional_mutation()
        except DuplicateKeyError:
            prior = await ledger_collection.find_one(
                {
                    "product_id": product_id,
                    "sku": sku,
                    "request_id": request_id,
                    "actor_user_id": actor_user_id,
                }
            )
            if not prior:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=Msg.DUPLICATE_IDEMPOTENCY_KEY_NO_RECORD,
                )
            if int(prior.get("delta", 0)) != delta or str(prior.get("reason", "")) != reason:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=Msg.IDEMPOTENCY_KEY_PAYLOAD_MISMATCH,
                )
        return await InventoryService.get_variant_inventory(product_id, sku, owner_seller_id)

    @staticmethod
    async def reserve_stock(product_id: PydanticObjectId, sku: str, quantity: int) -> None:
        """
        Move stock from available -> reserved
        Atomic operation (prevents race conditions)
        """
        InventoryDomainValidator.validate_sku(sku)
        InventoryDomainValidator.validate_operation_quantity(quantity)
        collection = Product.get_pymongo_collection()  # type: ignore

        result = await collection.update_one(
            {
                "_id": product_id,
                "is_deleted": {"$ne": True},
                "is_available": True,
                "variants": {
                    "$elemMatch": {
                        "sku": sku,
                        "available_stock": {"$gte": quantity}
                    }
                }
            },
            {
                "$inc": {
                    "variants.$.available_stock": -quantity,
                    "variants.$.reserved_stock": quantity
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock reservation failed for SKU {sku}"
            )

    @staticmethod
    async def confirm_stock_deduction(product_id: PydanticObjectId, sku: str, quantity: int) -> None:
        """
        Finalize stock after payment success
        (reserved_stock → burned permanently)
        """
        InventoryDomainValidator.validate_sku(sku)
        InventoryDomainValidator.validate_operation_quantity(quantity)
        collection = Product.get_pymongo_collection()  # type: ignore

        result = await collection.update_one(
            {
                "_id": product_id,
                "variants": {
                    "$elemMatch": {
                        "sku": sku,
                        "reserved_stock": {"$gte": quantity}
                    }
                }
            },
            {
                "$inc": {
                    "variants.$.reserved_stock": -quantity
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail=Msg.STOCK_CONFIRMATION_FAILED
            )

    @staticmethod
    async def release_reserved_stock(product_id: PydanticObjectId, sku: str, quantity: int) -> None:
        """
        Rollback stock (payment failed / crash recovery)
        """
        InventoryDomainValidator.validate_sku(sku)
        InventoryDomainValidator.validate_operation_quantity(quantity)
        collection = Product.get_pymongo_collection()  # type: ignore

        result = await collection.update_one(
            {
                "_id": product_id,
                "variants": {
                    "$elemMatch": {
                        "sku": sku,
                        "reserved_stock": {"$gte": quantity}
                    }
                }
            },
            {
                "$inc": {
                    "variants.$.available_stock": quantity,
                    "variants.$.reserved_stock": -quantity
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail=Msg.RESERVED_STOCK_RELEASE_FAILED
            )
    
    @staticmethod
    async def restore_stock(product_id: PydanticObjectId, sku: str, quantity: int) -> None:
        InventoryDomainValidator.validate_sku(sku)
        InventoryDomainValidator.validate_operation_quantity(quantity)
        collection = Product.get_pymongo_collection()  # type: ignore

        result = await collection.update_one(
            {
                "_id": product_id,
                "variants.sku": sku
            },
            {
                "$inc": {
                    "variants.$.available_stock": quantity
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail=Msg.STOCK_RESTORE_FAILED
            )
