import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MONGODB_URL = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "e_commerce"

KNOWN_VARIANT_KEYS = {
    "sku",
    "price",
    "discount_price",
    "discountPrice",
    "stock",
    "attributes",
    "qty",
    "quantity",
    "inventory",
    "mrp",
    "base_price",
    "list_price",
    "sale_price",
    "discount",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate products.variants to the current ProductVariant shape."
    )
    parser.add_argument(
        "--mongodb-url",
        default=os.getenv("MONGODB_URL", DEFAULT_MONGODB_URL),
        help="MongoDB connection string. Defaults to MONGODB_URL from .env.",
    )
    parser.add_argument(
        "--database-name",
        default=os.getenv("DATABASE_NAME", DEFAULT_DATABASE_NAME),
        help="MongoDB database name. Defaults to DATABASE_NAME from .env.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist updates. If omitted, the script runs in dry-run mode.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of products to scan (0 means all).",
    )
    return parser.parse_args()


def _as_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        num = int(value)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return None
    return num


def _as_non_negative_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 0
    try:
        num = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, num)


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _ensure_unique_sku(base_sku: str, seen: dict[str, int]) -> str:
    normalized = base_sku or "SKU"
    if normalized not in seen:
        seen[normalized] = 1
        return normalized

    seen[normalized] += 1
    return f"{normalized}-{seen[normalized]}"


def _build_attributes(raw_variant: dict[str, Any]) -> dict[str, str]:
    attrs = raw_variant.get("attributes")
    if isinstance(attrs, dict):
        cleaned: dict[str, str] = {}
        for key, value in attrs.items():
            key_text = _to_str(key)
            if not key_text:
                continue
            cleaned[key_text] = _to_str(value)
        return cleaned

    inferred: dict[str, str] = {}
    for key, value in raw_variant.items():
        if key in KNOWN_VARIANT_KEYS:
            continue
        key_text = _to_str(key)
        if not key_text:
            continue
        inferred[key_text] = _to_str(value)
    return inferred


def _normalize_variant(
    product_id_text: str,
    variant: Any,
    index: int,
    seen_skus: dict[str, int],
    fallback_price: int,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []

    if isinstance(variant, dict):
        raw_variant = variant
    else:
        raw_variant = {}
        warnings.append("variant-was-not-dict")

    raw_sku = _to_str(raw_variant.get("sku"))
    if not raw_sku:
        raw_sku = f"SKU-{product_id_text[:6]}-{index + 1}"
        warnings.append("sku-generated")

    sku = _ensure_unique_sku(raw_sku, seen_skus)
    if sku != raw_sku:
        warnings.append("sku-deduplicated")

    price = (
        _as_positive_int(raw_variant.get("price"))
        or _as_positive_int(raw_variant.get("mrp"))
        or _as_positive_int(raw_variant.get("base_price"))
        or _as_positive_int(raw_variant.get("list_price"))
        or _as_positive_int(raw_variant.get("sale_price"))
        or fallback_price
    )
    if price == fallback_price and _as_positive_int(raw_variant.get("price")) is None:
        warnings.append("price-fallback-used")

    discount_price = (
        _as_positive_int(raw_variant.get("discount_price"))
        or _as_positive_int(raw_variant.get("discountPrice"))
        or _as_positive_int(raw_variant.get("sale_price"))
    )

    if discount_price is not None and discount_price >= price:
        discount_price = None
        warnings.append("discount-price-reset")

    stock = (
        _as_non_negative_int(raw_variant.get("stock"))
        if "stock" in raw_variant
        else _as_non_negative_int(
            raw_variant.get("quantity", raw_variant.get("qty", raw_variant.get("inventory")))
        )
    )

    attributes = _build_attributes(raw_variant)

    normalized = {
        "sku": sku,
        "price": price,
        "discount_price": discount_price,
        "stock": stock,
        "attributes": attributes,
    }
    return normalized, warnings


def _effective_price(variant: dict[str, Any]) -> int:
    discount = variant.get("discount_price")
    if isinstance(discount, int) and discount > 0:
        return discount
    return int(variant["price"])


async def migrate(
    mongodb_url: str,
    database_name: str,
    apply: bool,
    limit: int,
) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    products = db["products"]

    scanned = 0
    changed = 0
    generated_variants = 0
    generated_skus = 0
    deduped_skus = 0
    reset_discounts = 0
    used_fallback_prices = 0

    operations: list[UpdateOne] = []

    try:
        cursor = products.find({}, {"variants": 1, "price": 1})
        async for doc in cursor:
            scanned += 1
            if limit > 0 and scanned > limit:
                break

            product_id = doc.get("_id")
            product_id_text = str(product_id)

            legacy_variants = doc.get("variants")
            fallback_price = _as_positive_int(doc.get("price")) or 1
            if not isinstance(legacy_variants, list) or len(legacy_variants) == 0:
                legacy_variants = [
                    {
                        "sku": f"SKU-{product_id_text[:6]}-1",
                        "price": fallback_price,
                        "discount_price": None,
                        "stock": 0,
                        "attributes": {},
                    }
                ]
                generated_variants += 1

            seen_skus: dict[str, int] = {}
            normalized_variants: list[dict[str, Any]] = []
            variant_warnings: list[str] = []

            for idx, raw_variant in enumerate(legacy_variants):
                normalized, warnings = _normalize_variant(
                    product_id_text=product_id_text,
                    variant=raw_variant,
                    index=idx,
                    seen_skus=seen_skus,
                    fallback_price=fallback_price,
                )
                normalized_variants.append(normalized)
                variant_warnings.extend(warnings)

            recomputed_price = min((_effective_price(v) for v in normalized_variants), default=fallback_price)

            if "sku-generated" in variant_warnings:
                generated_skus += 1
            if "sku-deduplicated" in variant_warnings:
                deduped_skus += 1
            if "discount-price-reset" in variant_warnings:
                reset_discounts += 1
            if "price-fallback-used" in variant_warnings:
                used_fallback_prices += 1

            if doc.get("variants") != normalized_variants or doc.get("price") != recomputed_price:
                changed += 1
                operations.append(
                    UpdateOne(
                        {"_id": product_id},
                        {
                            "$set": {
                                "variants": normalized_variants,
                                "price": recomputed_price,
                            }
                        },
                    )
                )

        print(f"Database: {database_name}")
        print(f"Scanned products: {scanned}")
        print(f"Products requiring update: {changed}")
        print(f"Generated fallback variant arrays: {generated_variants}")
        print(f"Variants with generated SKU: {generated_skus}")
        print(f"Variants with deduplicated SKU: {deduped_skus}")
        print(f"Variants with reset discount_price: {reset_discounts}")
        print(f"Variants with fallback price usage: {used_fallback_prices}")

        if not apply:
            print("Dry run mode (no changes written). Use --apply to persist updates.")
            return

        if not operations:
            print("No updates required.")
            return

        result = await products.bulk_write(operations, ordered=False)
        print(
            "Applied updates: "
            f"matched={result.matched_count} modified={result.modified_count}"
        )

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        migrate(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            apply=args.apply,
            limit=max(0, args.limit),
        )
    )
