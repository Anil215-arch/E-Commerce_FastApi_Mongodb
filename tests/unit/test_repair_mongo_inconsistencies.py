from datetime import datetime, timezone

from bson import ObjectId

from scripts.repair_mongo_inconsistencies import (
    DEFAULT_RATING_BREAKDOWN,
    aggregate_review_ratings,
    build_audit_actor_update,
    build_audit_update,
    normalize_address,
    normalize_cart_items,
    normalize_counter_key,
    normalize_counter_record,
    normalize_variant,
    product_rating_snapshot_from_breakdown,
)


def test_normalize_counter_key_trims_and_handles_none():
    assert normalize_counter_key("  invoice_2026  ") == "invoice_2026"
    assert normalize_counter_key(None) == ""


def test_normalize_counter_record_clamps_negative_sequence():
    record = normalize_counter_record({"_id": ObjectId(), "key": "  invoice_2026 ", "seq": -5})

    assert record["key"] == "invoice_2026"
    assert record["seq"] == 0


def test_build_audit_update_backfills_missing_fields_from_object_id():
    document_id = ObjectId()
    update = build_audit_update({"_id": document_id}, datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert update["created_at"] == document_id.generation_time.astimezone(timezone.utc)
    assert update["updated_at"] == document_id.generation_time.astimezone(timezone.utc)
    assert update["deleted_at"] is None
    assert update["created_by"] is None
    assert update["updated_by"] is None
    assert update["deleted_by"] is None
    assert update["is_deleted"] is False


def test_build_audit_actor_update_uses_user_id_for_user_documents():
    user_id = ObjectId()

    update = build_audit_actor_update("users", {"_id": user_id, "created_by": None, "updated_by": None}, None)

    assert update == {"created_by": user_id, "updated_by": user_id}


def test_build_audit_actor_update_uses_fallback_for_categories():
    admin_id = ObjectId()

    update = build_audit_actor_update("categories", {"_id": ObjectId(), "created_by": None}, admin_id)

    assert update == {"created_by": admin_id, "updated_by": admin_id}


def test_aggregate_review_ratings_builds_consistent_product_snapshot():
    snapshots = aggregate_review_ratings(
        [
            {"product_id": ObjectId("507f1f77bcf86cd799439011"), "rating": 5},
            {"product_id": ObjectId("507f1f77bcf86cd799439011"), "rating": 4},
            {"product_id": ObjectId("507f1f77bcf86cd799439011"), "rating": 4},
        ]
    )

    snapshot = snapshots[str(ObjectId("507f1f77bcf86cd799439011"))]
    assert snapshot["num_reviews"] == 3
    assert snapshot["rating_sum"] == 13
    assert snapshot["average_rating"] == 4.33
    assert snapshot["rating_breakdown"] == {
        **DEFAULT_RATING_BREAKDOWN,
        "4": 2,
        "5": 1,
    }


def test_normalize_variant_maps_legacy_stock_and_removes_bad_discount():
    variant = normalize_variant(
        {
            "sku": "  PHX-01  ",
            "price": "100",
            "discount_price": "120",
            "stock": "7",
            "attributes": {" Color ": " Black "},
        }
    )

    assert variant["sku"] == "PHX-01"
    assert variant["price"] == 100
    assert variant["discount_price"] is None
    assert variant["available_stock"] == 7
    assert variant["reserved_stock"] == 0
    assert variant["attributes"] == {"Color": "Black"}


def test_normalize_address_maps_legacy_field_names():
    address = normalize_address(
        {
            "name": "  Anil  ",
            "phone": "(987) 654-3210",
            "street": "  Main Road  ",
            "city": "  Bengaluru  ",
            "zip": "560001",
            "state": "KA",
            "country": "India",
        }
    )

    assert address["full_name"] == "Anil"
    assert address["phone_number"] == "9876543210"
    assert address["street_address"] == "Main Road"
    assert address["postal_code"] == "560001"


def test_normalize_cart_items_drops_invalid_and_deduplicates():
    product_id = ObjectId()
    items = normalize_cart_items(
        [
            {"product_id": product_id, "sku": "SKU-1", "quantity": 20},
            {"product_id": str(product_id), "sku": "SKU-1", "quantity": 2},
            {"product_id": "not-an-object-id", "sku": "SKU-2", "quantity": 1},
            {"product_id": ObjectId(), "sku": "BAD SKU!*", "quantity": 1},
        ]
    )

    assert items == [{"product_id": product_id, "sku": "SKU-1", "quantity": 10}]


def test_product_rating_snapshot_from_breakdown_recomputes_model_fields():
    snapshot = product_rating_snapshot_from_breakdown({"1": "1", "5": 3, "bad": 10})

    assert snapshot["num_reviews"] == 4
    assert snapshot["rating_sum"] == 16
    assert snapshot["average_rating"] == 4.0
    assert snapshot["rating_breakdown"] == {"1": 1, "2": 0, "3": 0, "4": 0, "5": 3}
