from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.core.config import settings


AUDIT_COLLECTIONS = [
    "products",
    "categories",
    "users",
    "orders",
    "transactions",
    "inventory_ledger",
    "wishlists",
    "reviews",
    "device_tokens",
    "notifications",
]

DEFAULT_RATING_BREAKDOWN = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
VALID_USER_ROLES = {"super_admin", "admin", "seller", "customer", "support"}
VALID_ORDER_STATUSES = {"PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "COMPLETED", "CANCELLED"}
VALID_ORDER_PAYMENT_STATUSES = {"PENDING", "PAID", "FAILED", "PARTIALLY_REFUNDED", "REFUNDED"}
VALID_TRANSACTION_STATUSES = {"PENDING", "SUCCESS", "FAILED", "PARTIALLY_REFUNDED", "REFUNDED"}
VALID_PAYMENT_METHODS = {"CARD", "UPI"}
VALID_NOTIFICATION_TYPES = {"ORDER", "PAYMENT", "SYSTEM", "PROMOTION"}
VALID_DEVICE_PLATFORMS = {"IOS", "ANDROID", "WEB", "UNKNOWN"}
VALID_OTP_PURPOSES = {"registration", "password_reset"}

DEFAULT_ADDRESS = {
    "full_name": "Unknown User",
    "phone_number": "9999999999",
    "street_address": "Unknown Address",
    "city": "Unknown",
    "postal_code": "000000",
    "state": "Unknown",
    "country": "India",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair legacy MongoDB documents so they match the current model contracts."
    )
    parser.add_argument("--mongodb-url", default=os.getenv("MONGODB_URL", settings.MONGODB_URL))
    parser.add_argument("--database", default=os.getenv("DATABASE_NAME", settings.DATABASE_NAME))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the repairs back to MongoDB. Without this flag the script only prints a summary.",
    )
    parser.add_argument(
        "--audit-actor-id",
        default=os.getenv("AUDIT_ACTOR_ID"),
        help=(
            "ObjectId to use when backfilling null created_by/updated_by fields. "
            "Defaults to the first super_admin/admin user when available."
        ),
    )
    return parser.parse_args()


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _document_created_at(document: Mapping[str, Any], fallback: datetime) -> datetime:
    created_at = document.get("created_at")
    if isinstance(created_at, datetime):
        return _ensure_timezone(created_at)

    document_id = document.get("_id")
    if isinstance(document_id, ObjectId):
        return _ensure_timezone(document_id.generation_time)

    return fallback


def _clean_string(value: Any, default: str = "", *, title: bool = False, upper: bool = False, lower: bool = False) -> str:
    text = str(value).strip() if value is not None else default
    if not text:
        text = default
    if title:
        text = text.title()
    if upper:
        text = text.upper()
    if lower:
        text = text.lower()
    return text


def _clean_int(value: Any, default: int = 0, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(number, minimum)
    if maximum is not None:
        number = min(number, maximum)
    return number


def _clean_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default


def _clean_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    if value is None:
        return None
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _clean_datetime(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return _ensure_timezone(value)
    return fallback


def _clean_enum(value: Any, allowed: set[str], default: str, *, upper: bool = False, lower: bool = False) -> str:
    candidate = _clean_string(value, default, upper=upper, lower=lower)
    return candidate if candidate in allowed else default


def _clean_string_list(value: Any, *, max_items: int | None = None, max_length: int = 500) -> list[str]:
    if not isinstance(value, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_string(item)[:max_length]
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
        if max_items is not None and len(cleaned) >= max_items:
            break
    return cleaned


def _clean_string_dict(value: Any, *, max_key_length: int = 50, max_value_length: int = 500) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}

    cleaned: dict[str, str] = {}
    for key, raw_value in value.items():
        clean_key = _clean_string(key)[:max_key_length]
        if not clean_key:
            continue
        cleaned[clean_key] = _clean_string(raw_value)[:max_value_length]
    return cleaned


def _build_set_update(document: Mapping[str, Any], normalized: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in normalized.items() if document.get(key) != value}


def _normalize_phone(value: Any) -> str:
    text = _clean_string(value)
    if re.fullmatch(r"\+?[1-9]\d{9,14}", text):
        return text

    digits = re.sub(r"\D", "", text)
    if len(digits) >= 10:
        digits = digits[-10:]
        if digits[0] != "0":
            return digits
    return "9999999999"


def normalize_address(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return DEFAULT_ADDRESS.copy()

    address = {
        "full_name": _clean_string(value.get("full_name") or value.get("name"), DEFAULT_ADDRESS["full_name"])[:100],
        "phone_number": _normalize_phone(value.get("phone_number") or value.get("phone") or value.get("mobile")),
        "street_address": _clean_string(
            value.get("street_address") or value.get("street") or value.get("address"),
            DEFAULT_ADDRESS["street_address"],
        )[:255],
        "city": _clean_string(value.get("city"), DEFAULT_ADDRESS["city"])[:100],
        "postal_code": _clean_string(value.get("postal_code") or value.get("zip") or value.get("pincode"), DEFAULT_ADDRESS["postal_code"])[:20],
        "state": _clean_string(value.get("state"), DEFAULT_ADDRESS["state"])[:100],
        "country": _clean_string(value.get("country"), DEFAULT_ADDRESS["country"])[:100],
    }

    for field, default in DEFAULT_ADDRESS.items():
        min_length = 4 if field == "postal_code" else 2
        if len(address[field]) < min_length:
            address[field] = default
    return address


def normalize_variant(value: Any, index: int = 0) -> dict[str, Any]:
    data = value if isinstance(value, Mapping) else {}
    sku = _clean_string(data.get("sku"), f"SKU-{index + 1}")[:50]
    if len(sku) < 3:
        sku = f"{sku}-SKU"[:50]

    price = _clean_int(data.get("price"), 1, minimum=1)
    raw_discount = data.get("discount_price")
    discount_price = _clean_int(raw_discount, 0, minimum=1) if raw_discount is not None else None
    if discount_price is not None and discount_price >= price:
        discount_price = None

    available_stock = _clean_int(data.get("available_stock", data.get("stock", 0)), 0, minimum=0)
    reserved_stock = _clean_int(data.get("reserved_stock", 0), 0, minimum=0)

    return {
        "sku": sku,
        "price": price,
        "discount_price": discount_price,
        "available_stock": available_stock,
        "reserved_stock": reserved_stock,
        "attributes": _clean_string_dict(data.get("attributes"), max_key_length=50, max_value_length=200),
    }


def normalize_variants(value: Any) -> list[dict[str, Any]]:
    raw_variants = value if isinstance(value, list) else []
    variants: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, raw_variant in enumerate(raw_variants[:100]):
        variant = normalize_variant(raw_variant, index)
        original_sku = variant["sku"]
        suffix = 2
        while variant["sku"] in seen:
            variant["sku"] = f"{original_sku}-{suffix}"[:50]
            suffix += 1
        variants.append(variant)
        seen.add(variant["sku"])

    if not variants:
        variants.append(normalize_variant({}, 0))
    return variants


def normalize_rating_breakdown(value: Any) -> dict[str, int]:
    source = value if isinstance(value, Mapping) else {}
    return {key: _clean_int(source.get(key, 0), 0, minimum=0) for key in DEFAULT_RATING_BREAKDOWN}


def product_rating_snapshot_from_breakdown(value: Any) -> dict[str, Any]:
    breakdown = normalize_rating_breakdown(value)
    num_reviews = sum(breakdown.values())
    rating_sum = sum(int(key) * count for key, count in breakdown.items())
    average_rating = round(rating_sum / num_reviews, 2) if num_reviews else 0.0
    return {
        "num_reviews": num_reviews,
        "rating_sum": rating_sum,
        "rating_breakdown": breakdown,
        "average_rating": average_rating,
    }


def build_audit_update(document: Mapping[str, Any], fallback: datetime) -> dict[str, Any]:
    created_at = _document_created_at(document, fallback)
    updated_at = document.get("updated_at")
    if not isinstance(updated_at, datetime):
        updated_at = created_at
    else:
        updated_at = _ensure_timezone(updated_at)

    update: dict[str, Any] = {}
    if document.get("created_at") is None:
        update["created_at"] = created_at
    if document.get("updated_at") is None:
        update["updated_at"] = updated_at

    for field in ("deleted_at", "created_by", "updated_by", "deleted_by"):
        if field not in document:
            update[field] = None

    if "is_deleted" not in document:
        update["is_deleted"] = False

    return update


def resolve_audit_actor_id(db, explicit_actor_id: Any = None) -> ObjectId | None:
    explicit = _clean_object_id(explicit_actor_id)
    if explicit is not None:
        return explicit

    actor = db["users"].find_one(
        {"role": {"$in": ["super_admin", "admin"]}, "is_deleted": {"$ne": True}},
        {"_id": 1},
        sort=[("role", -1), ("created_at", 1)],
    )
    if actor is not None:
        return actor["_id"]

    actor = db["users"].find_one({"is_deleted": {"$ne": True}}, {"_id": 1}, sort=[("created_at", 1)])
    return actor["_id"] if actor is not None else None


def build_audit_actor_update(
    collection_name: str,
    document: Mapping[str, Any],
    fallback_actor_id: ObjectId | None,
) -> dict[str, Any]:
    if collection_name == "users":
        actor_id = _clean_object_id(document.get("_id"))
    elif collection_name == "products":
        actor_id = (
            _clean_object_id(document.get("created_by"))
            or _clean_object_id(document.get("seller_id"))
            or fallback_actor_id
        )
    elif collection_name == "orders":
        actor_id = _clean_object_id(document.get("user_id")) or fallback_actor_id
    elif collection_name == "transactions":
        actor_id = _clean_object_id(document.get("user_id")) or fallback_actor_id
    elif collection_name == "inventory_ledger":
        actor_id = (
            _clean_object_id(document.get("actor_user_id"))
            or _clean_object_id(document.get("user_id"))
            or fallback_actor_id
        )
    elif collection_name in {"wishlists", "reviews", "device_tokens", "notifications"}:
        actor_id = _clean_object_id(document.get("user_id")) or fallback_actor_id
    else:
        actor_id = fallback_actor_id

    if actor_id is None:
        return {}

    update: dict[str, Any] = {}
    if document.get("created_by") is None:
        update["created_by"] = actor_id
    if document.get("updated_by") is None:
        update["updated_by"] = actor_id
    return update


def normalize_counter_key(key: Any) -> str:
    return str(key).strip() if key is not None else ""


def normalize_counter_record(document: Mapping[str, Any]) -> dict[str, Any]:
    seq_value = document.get("seq", 0)
    try:
        seq = int(seq_value)
    except (TypeError, ValueError):
        seq = 0

    return {
        "_id": document["_id"],
        "key": normalize_counter_key(document.get("key")),
        "seq": max(seq, 0),
    }


def aggregate_review_ratings(reviews: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    aggregates: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "num_reviews": 0,
            "rating_sum": 0,
            "rating_breakdown": DEFAULT_RATING_BREAKDOWN.copy(),
            "average_rating": 0.0,
        }
    )

    for review in reviews:
        product_id = review.get("product_id")
        rating = review.get("rating")
        if product_id is None or rating is None:
            continue

        try:
            rating_value = int(rating)
        except (TypeError, ValueError):
            continue

        if rating_value < 1 or rating_value > 5:
            continue

        bucket = aggregates[str(product_id)]
        bucket["num_reviews"] += 1
        bucket["rating_sum"] += rating_value
        bucket["rating_breakdown"][str(rating_value)] += 1

    for bucket in aggregates.values():
        if bucket["num_reviews"] > 0:
            bucket["average_rating"] = round(bucket["rating_sum"] / bucket["num_reviews"], 2)

    return aggregates


def repair_audit_collections(
    db,
    *,
    dry_run: bool,
    fallback: datetime,
    audit_actor_id: ObjectId | None = None,
) -> dict[str, int]:
    repaired_counts: dict[str, int] = {}
    for collection_name in AUDIT_COLLECTIONS:
        collection = db[collection_name]
        repaired = 0
        for document in collection.find(
            {},
            {
                "created_at": 1,
                "updated_at": 1,
                "deleted_at": 1,
                "created_by": 1,
                "updated_by": 1,
                "deleted_by": 1,
                "is_deleted": 1,
                "seller_id": 1,
                "user_id": 1,
                "actor_user_id": 1,
            },
        ):
            update = build_audit_update(document, fallback)
            update.update(build_audit_actor_update(collection_name, document, audit_actor_id))
            if not update:
                continue

            repaired += 1
            if not dry_run:
                collection.update_one({"_id": document["_id"]}, {"$set": update})

        repaired_counts[collection_name] = repaired

    return repaired_counts


def repair_product_ratings(db, *, dry_run: bool) -> int:
    reviews = db["reviews"].find({}, {"product_id": 1, "rating": 1})
    aggregates = aggregate_review_ratings(reviews)

    repaired = 0
    products = db["products"].find({}, {"rating": 1, "num_reviews": 1, "rating_sum": 1, "average_rating": 1, "rating_breakdown": 1})
    for product in products:
        product_id = str(product["_id"])
        aggregate = aggregates.get(
            product_id,
            {
                "num_reviews": 0,
                "rating_sum": 0,
                "rating_breakdown": DEFAULT_RATING_BREAKDOWN.copy(),
                "average_rating": 0.0,
            },
        )

        update: dict[str, Any] = {}
        for field in ("num_reviews", "rating_sum", "average_rating", "rating_breakdown"):
            if product.get(field) != aggregate[field]:
                update[field] = aggregate[field]

        unset_fields: dict[str, str] = {}
        if "rating" in product:
            unset_fields["rating"] = ""

        if update or unset_fields:
            repaired += 1
            if not dry_run:
                payload: dict[str, Any] = {}
                if update:
                    payload["$set"] = update
                if unset_fields:
                    payload["$unset"] = unset_fields
                db["products"].update_one({"_id": product["_id"]}, payload)

    return repaired


def repair_counters(db, *, dry_run: bool) -> dict[str, int]:
    collection = db["counters"]
    documents = list(collection.find({}, {"key": 1, "seq": 1}))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    removed_invalid = 0
    for document in documents:
        normalized = normalize_counter_record(document)
        if not normalized["key"]:
            removed_invalid += 1
            if not dry_run:
                collection.delete_one({"_id": normalized["_id"]})
            continue

        grouped[normalized["key"]].append(normalized)

    updated_docs = 0
    removed_duplicates = 0
    for key, records in grouped.items():
        winner = max(records, key=lambda item: (item["seq"], str(item["_id"])))
        original = next(document for document in documents if document["_id"] == winner["_id"])
        current_key = normalize_counter_key(original.get("key"))
        current_seq_raw = original.get("seq", 0)
        try:
            current_seq = int(current_seq_raw)
        except (TypeError, ValueError):
            current_seq = 0

        if current_key != key or max(current_seq, 0) != winner["seq"]:
            updated_docs += 1
            if not dry_run:
                collection.update_one(
                    {"_id": winner["_id"]},
                    {"$set": {"key": key, "seq": winner["seq"]}},
                )

        duplicate_ids = [record["_id"] for record in records if record["_id"] != winner["_id"]]
        removed_duplicates += len(duplicate_ids)
        if duplicate_ids and not dry_run:
            collection.delete_many({"_id": {"$in": duplicate_ids}})

    return {
        "updated": updated_docs,
        "removed_invalid": removed_invalid,
        "removed_duplicates": removed_duplicates,
    }


def repair_categories(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["categories"].find({}, {"name": 1, "parent_id": 1}):
        parent_id = _clean_object_id(document.get("parent_id"))
        if parent_id == document.get("_id"):
            parent_id = None
        normalized = {
            "name": _clean_string(document.get("name"), "Uncategorized")[:100],
            "parent_id": parent_id,
        }
        if len(normalized["name"]) < 2:
            normalized["name"] = "Uncategorized"

        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["categories"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_products(db, *, dry_run: bool) -> int:
    repaired = 0
    projection = {
        "name": 1,
        "description": 1,
        "brand": 1,
        "category_id": 1,
        "variants": 1,
        "price": 1,
        "images": 1,
        "specifications": 1,
        "is_available": 1,
        "is_featured": 1,
        "created_by": 1,
        "seller_id": 1,
    }
    for document in db["products"].find({}, projection):
        variants = normalize_variants(document.get("variants"))
        effective_prices = [
            variant["discount_price"] if variant["discount_price"] else variant["price"]
            for variant in variants
            if (variant["discount_price"] if variant["discount_price"] else variant["price"]) > 0
        ]
        seller_id = _clean_object_id(document.get("seller_id")) or _clean_object_id(document.get("created_by"))
        normalized: dict[str, Any] = {
            "name": _clean_string(document.get("name"), "Untitled Product")[:200],
            "description": _clean_string(document.get("description"), "Product description unavailable.")[:5000],
            "brand": _clean_string(document.get("brand"), "Generic", title=True)[:100],
            "category_id": _clean_object_id(document.get("category_id")),
            "variants": variants,
            "price": min(effective_prices, default=0),
            "images": _clean_string_list(document.get("images"), max_items=20),
            "specifications": _clean_string_dict(document.get("specifications")),
            "is_available": _clean_bool(document.get("is_available"), True),
            "is_featured": _clean_bool(document.get("is_featured"), False),
        }
        if seller_id is not None:
            normalized["seller_id"] = seller_id
        if len(normalized["name"]) < 3:
            normalized["name"] = "Untitled Product"
        if len(normalized["description"]) < 10:
            normalized["description"] = "Product description unavailable."
        if len(normalized["brand"]) < 2:
            normalized["brand"] = "Generic"

        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["products"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_users(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["users"].find({}, {"user_name": 1, "email": 1, "mobile": 1, "role": 1, "is_verified": 1, "addresses": 1}):
        raw_addresses = document.get("addresses") if isinstance(document.get("addresses"), list) else []
        normalized = {
            "user_name": _clean_string(document.get("user_name"), "User")[:100],
            "email": _clean_string(document.get("email"), "unknown@example.com", lower=True)[:254],
            "mobile": _normalize_phone(document.get("mobile")),
            "role": _clean_enum(document.get("role"), VALID_USER_ROLES, "customer", lower=True),
            "is_verified": _clean_bool(document.get("is_verified"), False),
            "addresses": [normalize_address(address) for address in raw_addresses[:10]],
        }
        if len(normalized["user_name"]) < 2 or not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_ -]+$", normalized["user_name"]):
            normalized["user_name"] = f"User {str(document['_id'])[-6:]}"

        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["users"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def normalize_cart_items(value: Any) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items[:20]:
        if not isinstance(item, Mapping):
            continue
        product_id = _clean_object_id(item.get("product_id"))
        if product_id is None:
            continue
        sku = _clean_string(item.get("sku"))[:50]
        if len(sku) < 3 or not re.fullmatch(r"[A-Za-z0-9\-_]+", sku):
            continue
        key = (str(product_id), sku)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "product_id": product_id,
                "sku": sku,
                "quantity": _clean_int(item.get("quantity", 1), 1, minimum=1, maximum=10),
            }
        )
    return normalized


def repair_carts(db, *, dry_run: bool, fallback: datetime) -> int:
    repaired = 0
    for document in db["carts"].find({}, {"user_id": 1, "items": 1, "version": 1, "updated_at": 1}):
        user_id = _clean_object_id(document.get("user_id"))
        if user_id is None:
            continue
        normalized = {
            "user_id": user_id,
            "items": normalize_cart_items(document.get("items")),
            "version": _clean_int(document.get("version", 1), 1, minimum=1),
            "updated_at": _clean_datetime(document.get("updated_at"), fallback),
        }
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["carts"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_wishlists(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["wishlists"].find({}, {"user_id": 1, "product_id": 1, "sku": 1}):
        user_id = _clean_object_id(document.get("user_id"))
        product_id = _clean_object_id(document.get("product_id"))
        if user_id is None or product_id is None:
            continue
        sku = _clean_string(document.get("sku"), "SKU-1")[:100]
        if len(sku) < 3:
            sku = "SKU-1"
        normalized = {"user_id": user_id, "product_id": product_id, "sku": sku}
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["wishlists"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_reviews(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["reviews"].find({}, {"product_id": 1, "user_id": 1, "rating": 1, "review": 1, "is_verified": 1, "images": 1, "order_id": 1}):
        product_id = _clean_object_id(document.get("product_id"))
        user_id = _clean_object_id(document.get("user_id"))
        if product_id is None or user_id is None:
            continue
        review = document.get("review")
        clean_review = _clean_string(review)[:1000] if review is not None else None
        if clean_review == "":
            clean_review = None
        normalized = {
            "product_id": product_id,
            "user_id": user_id,
            "rating": _clean_int(document.get("rating", 1), 1, minimum=1, maximum=5),
            "review": clean_review,
            "is_verified": _clean_bool(document.get("is_verified"), False),
            "images": _clean_string_list(document.get("images"), max_items=5),
            "order_id": _clean_object_id(document.get("order_id")) if document.get("order_id") is not None else None,
        }
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["reviews"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def normalize_order_items(value: Any, default_seller_id: ObjectId | None = None) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            continue
        product_id = _clean_object_id(item.get("product_id"))
        seller_id = _clean_object_id(item.get("seller_id")) or default_seller_id
        if product_id is None or seller_id is None:
            continue
        sku = _clean_string(item.get("sku"), f"SKU-{index + 1}")
        if len(sku) < 3:
            sku = f"SKU-{index + 1}"
        normalized.append(
            {
                "product_id": product_id,
                "seller_id": seller_id,
                "sku": sku,
                "product_name": _clean_string(item.get("product_name") or item.get("name"), "Product")[:200],
                "quantity": _clean_int(item.get("quantity", 1), 1, minimum=1),
                "purchase_price": _clean_int(item.get("purchase_price", item.get("price", 0)), 0, minimum=0),
            }
        )
    return normalized


def _order_totals_from_items(items: list[dict[str, Any]], document: Mapping[str, Any]) -> dict[str, int]:
    subtotal = sum(item["purchase_price"] * item["quantity"] for item in items)
    subtotal = _clean_int(document.get("subtotal", subtotal), subtotal, minimum=0)
    tax_amount = _clean_int(document.get("tax_amount", 0), 0, minimum=0)
    shipping_fee = _clean_int(document.get("shipping_fee", 0), 0, minimum=0)
    expected_total = subtotal + tax_amount + shipping_fee
    grand_total = _clean_int(document.get("grand_total", expected_total), expected_total, minimum=0)
    if grand_total != expected_total:
        grand_total = expected_total
    return {
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "shipping_fee": shipping_fee,
        "grand_total": grand_total,
    }


def repair_orders(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["orders"].find({}):
        user_id = _clean_object_id(document.get("user_id"))
        seller_id = _clean_object_id(document.get("seller_id"))
        transaction_id = _clean_object_id(document.get("transaction_id"))
        if user_id is None or seller_id is None or transaction_id is None:
            continue
        items = normalize_order_items(document.get("items"), seller_id)
        if not items:
            continue
        totals = _order_totals_from_items(items, document)
        normalized: dict[str, Any] = {
            "user_id": user_id,
            "seller_id": seller_id,
            "checkout_batch_id": _clean_string(document.get("checkout_batch_id"), f"batch-{document['_id']}"),
            "transaction_id": transaction_id,
            "items": items,
            "shipping_address": normalize_address(document.get("shipping_address")),
            "billing_address": normalize_address(document.get("billing_address")),
            "status": _clean_enum(document.get("status"), VALID_ORDER_STATUSES, "PENDING", upper=True),
            "payment_status": _clean_enum(document.get("payment_status"), VALID_ORDER_PAYMENT_STATUSES, "PENDING", upper=True),
            "refunded_amount": _clean_int(document.get("refunded_amount", 0), 0, minimum=0),
            "expires_at": _clean_object_id(None) if document.get("expires_at") is None else document.get("expires_at"),
            "cleanup_processed": _clean_bool(document.get("cleanup_processed"), False),
            "cancellation_reason": document.get("cancellation_reason"),
            **totals,
        }
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["orders"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_transactions(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["transactions"].find({}):
        user_id = _clean_object_id(document.get("user_id"))
        if user_id is None:
            continue
        allocations = []
        for allocation in document.get("allocations", []) if isinstance(document.get("allocations"), list) else []:
            if not isinstance(allocation, Mapping):
                continue
            order_id = _clean_object_id(allocation.get("order_id"))
            seller_id = _clean_object_id(allocation.get("seller_id"))
            if order_id is None or seller_id is None:
                continue
            allocations.append(
                {
                    "order_id": order_id,
                    "seller_id": seller_id,
                    "amount": _clean_int(allocation.get("amount", 0), 0, minimum=0),
                    "refunded_amount": _clean_int(allocation.get("refunded_amount", 0), 0, minimum=0),
                }
            )
        normalized = {
            "user_id": user_id,
            "checkout_batch_id": _clean_string(document.get("checkout_batch_id"), f"batch-{document['_id']}"),
            "amount": _clean_int(document.get("amount", 0), 0, minimum=0),
            "refunded_amount": _clean_int(document.get("refunded_amount", 0), 0, minimum=0),
            "status": _clean_enum(document.get("status"), VALID_TRANSACTION_STATUSES, "PENDING", upper=True),
            "payment_method": _clean_enum(document.get("payment_method"), VALID_PAYMENT_METHODS, "CARD", upper=True),
            "gateway_transaction_id": document.get("gateway_transaction_id") or None,
            "allocations": allocations,
        }
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["transactions"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_invoices(db, *, dry_run: bool, fallback: datetime) -> int:
    repaired = 0
    for document in db["invoices"].find({}):
        order_id = _clean_object_id(document.get("order_id"))
        transaction_id = _clean_object_id(document.get("transaction_id"))
        user_id = _clean_object_id(document.get("user_id"))
        if order_id is None or transaction_id is None or user_id is None:
            continue
        items = normalize_order_items(document.get("items"))
        if not items:
            continue
        totals = _order_totals_from_items(items, document)
        normalized = {
            "invoice_number": _clean_string(document.get("invoice_number"), f"INV-{str(document['_id'])[-8:]}"),
            "order_id": order_id,
            "transaction_id": transaction_id,
            "user_id": user_id,
            "items": items,
            "shipping_address": normalize_address(document.get("shipping_address")),
            "billing_address": normalize_address(document.get("billing_address")),
            "currency": _clean_string(document.get("currency"), "INR").upper(),
            "payment_method": _clean_enum(document.get("payment_method"), VALID_PAYMENT_METHODS, "CARD", upper=True),
            "gateway_transaction_id": document.get("gateway_transaction_id") or None,
            "issued_at": _clean_datetime(document.get("issued_at"), fallback),
            **totals,
        }
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["invoices"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_inventory_ledger(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["inventory_ledger"].find({}):
        product_id = _clean_object_id(document.get("product_id"))
        actor_user_id = _clean_object_id(document.get("actor_user_id")) or _clean_object_id(document.get("user_id"))
        owner_seller_id = _clean_object_id(document.get("owner_seller_id")) or actor_user_id
        if product_id is None or actor_user_id is None or owner_seller_id is None:
            continue
        previous_stock = _clean_int(document.get("previous_stock", 0), 0, minimum=0)
        delta = _clean_int(document.get("delta", 1), 1)
        if delta == 0:
            delta = 1
        new_stock = max(previous_stock + delta, 0)
        normalized = {
            "product_id": product_id,
            "sku": _clean_string(document.get("sku"), "SKU-1")[:120],
            "user_id": actor_user_id,
            "actor_user_id": actor_user_id,
            "owner_seller_id": owner_seller_id,
            "request_id": _clean_string(document.get("request_id"), f"repair-{document['_id']}")[:120],
            "delta": delta,
            "previous_stock": previous_stock,
            "new_stock": new_stock,
            "reason": _clean_string(document.get("reason"), "data repair migration")[:200],
        }
        if len(normalized["sku"]) < 1:
            normalized["sku"] = "SKU-1"
        if len(normalized["request_id"]) < 8:
            normalized["request_id"] = f"repair-{document['_id']}"
        if len(normalized["reason"]) < 5:
            normalized["reason"] = "data repair migration"

        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["inventory_ledger"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_notifications(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["notifications"].find({}, {"user_id": 1, "title": 1, "message": 1, "type": 1, "is_read": 1, "metadata": 1}):
        user_id = _clean_object_id(document.get("user_id"))
        if user_id is None:
            continue
        normalized = {
            "user_id": user_id,
            "title": _clean_string(document.get("title"), "Notification")[:150],
            "message": _clean_string(document.get("message"), "Notification message unavailable.")[:1000],
            "type": _clean_enum(document.get("type"), VALID_NOTIFICATION_TYPES, "SYSTEM", upper=True),
            "is_read": _clean_bool(document.get("is_read"), False),
            "metadata": dict(document.get("metadata")) if isinstance(document.get("metadata"), Mapping) else {},
        }
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["notifications"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_device_tokens(db, *, dry_run: bool) -> int:
    repaired = 0
    for document in db["device_tokens"].find({}, {"user_id": 1, "token": 1, "platform": 1}):
        user_id = _clean_object_id(document.get("user_id"))
        token = _clean_string(document.get("token"))
        if user_id is None or len(token) < 10:
            continue
        normalized = {
            "user_id": user_id,
            "token": token[:512],
            "platform": _clean_enum(document.get("platform"), VALID_DEVICE_PLATFORMS, "UNKNOWN", upper=True),
        }
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["device_tokens"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_email_otps(db, *, dry_run: bool, fallback: datetime) -> int:
    repaired = 0
    for document in db["email_otp_verifications"].find({}):
        created_at = _clean_datetime(document.get("created_at"), fallback)
        expires_at = document.get("expires_at")
        if not isinstance(expires_at, datetime) or _ensure_timezone(expires_at) <= created_at:
            expires_at = created_at.replace(year=created_at.year + 1)
        normalized = {
            "email": _clean_string(document.get("email"), "unknown@example.com", lower=True)[:254],
            "hashed_otp": _clean_string(document.get("hashed_otp"), "repair-placeholder-hashed-otp")[:500],
            "purpose": _clean_enum(document.get("purpose"), VALID_OTP_PURPOSES, "registration", lower=True),
            "created_at": created_at,
            "expires_at": _ensure_timezone(expires_at),
            "attempts": _clean_int(document.get("attempts", 0), 0, minimum=0),
        }
        if len(normalized["hashed_otp"]) < 20:
            normalized["hashed_otp"] = "repair-placeholder-hashed-otp"
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["email_otp_verifications"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def repair_revoked_tokens(db, *, dry_run: bool, fallback: datetime) -> int:
    repaired = 0
    for document in db["revoked_tokens"].find({}):
        created_at = _clean_datetime(document.get("created_at"), fallback)
        expires_at = document.get("expires_at")
        if not isinstance(expires_at, datetime) or _ensure_timezone(expires_at) <= created_at:
            expires_at = created_at.replace(year=created_at.year + 1)
        normalized = {
            "jti": _clean_string(document.get("jti"), f"repair-{document['_id']}"),
            "token_type": _clean_enum(document.get("token_type"), {"access", "refresh"}, "access", lower=True),
            "user_id": _clean_string(document.get("user_id")) if document.get("user_id") is not None else None,
            "expires_at": _ensure_timezone(expires_at),
            "created_at": created_at,
        }
        update = _build_set_update(document, normalized)
        if update:
            repaired += 1
            if not dry_run:
                db["revoked_tokens"].update_one({"_id": document["_id"]}, {"$set": update})
    return repaired


def main() -> int:
    args = parse_args()
    client = MongoClient(args.mongodb_url, tz_aware=True)
    db = client[args.database]
    dry_run = not args.apply
    now = datetime.now(timezone.utc)
    audit_actor_id = resolve_audit_actor_id(db, args.audit_actor_id)

    audit_counts = repair_audit_collections(
        db,
        dry_run=dry_run,
        fallback=now,
        audit_actor_id=audit_actor_id,
    )
    collection_counts = {
        "categories": repair_categories(db, dry_run=dry_run),
        "products": repair_products(db, dry_run=dry_run),
        "users": repair_users(db, dry_run=dry_run),
        "carts": repair_carts(db, dry_run=dry_run, fallback=now),
        "wishlists": repair_wishlists(db, dry_run=dry_run),
        "reviews": repair_reviews(db, dry_run=dry_run),
        "orders": repair_orders(db, dry_run=dry_run),
        "transactions": repair_transactions(db, dry_run=dry_run),
        "invoices": repair_invoices(db, dry_run=dry_run, fallback=now),
        "inventory_ledger": repair_inventory_ledger(db, dry_run=dry_run),
        "notifications": repair_notifications(db, dry_run=dry_run),
        "device_tokens": repair_device_tokens(db, dry_run=dry_run),
        "email_otp_verifications": repair_email_otps(db, dry_run=dry_run, fallback=now),
        "revoked_tokens": repair_revoked_tokens(db, dry_run=dry_run, fallback=now),
    }
    product_rating_count = repair_product_ratings(db, dry_run=dry_run)
    counter_counts = repair_counters(db, dry_run=dry_run)

    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"[{mode}] audit actor id: {audit_actor_id}")
    print(f"[{mode}] audit collections: {audit_counts}")
    print(f"[{mode}] model collections repaired: {collection_counts}")
    print(f"[{mode}] product rating snapshots repaired: {product_rating_count}")
    print(f"[{mode}] counters repaired: {counter_counts}")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
