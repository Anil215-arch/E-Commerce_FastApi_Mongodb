import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MONGODB_URL = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "e_commerce"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and optionally reconcile product variant inventory invariants."
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
        "--sample-limit",
        type=int,
        default=10,
        help="How many sample violating variants to print.",
    )
    parser.add_argument(
        "--apply-fixes",
        action="store_true",
        help="Apply conservative fixes for missing/invalid stock fields.",
    )
    return parser.parse_args()


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def reconcile_inventory_invariants(
    mongodb_url: str,
    database_name: str,
    sample_limit: int,
    apply_fixes: bool,
) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    products = db["products"]

    total_products = 0
    products_with_issues = 0
    variant_issues = 0
    fixed_products = 0
    fixed_variants = 0
    samples: list[dict[str, Any]] = []

    try:
        async for product in products.find({}, {"variants": 1}):
            total_products += 1
            product_id = str(product.get("_id"))
            raw_variants = product.get("variants")

            if not isinstance(raw_variants, list):
                continue

            has_issue = False
            updated_variants: list[dict[str, Any]] = []
            product_fixed_variant_count = 0

            for idx, variant in enumerate(raw_variants):
                if not isinstance(variant, dict):
                    has_issue = True
                    variant_issues += 1
                    if len(samples) < sample_limit:
                        samples.append(
                            {
                                "product_id": product_id,
                                "index": idx,
                                "sku": None,
                                "issue": "variant is not an object",
                            }
                        )
                    if apply_fixes:
                        product_fixed_variant_count += 1
                        updated_variants.append(
                            {
                                "sku": f"MISSING-SKU-{idx+1}",
                                "price": 1,
                                "discount_price": None,
                                "available_stock": 0,
                                "reserved_stock": 0,
                                "attributes": {},
                            }
                        )
                    else:
                        updated_variants.append(variant)
                    continue

                sku = str(variant.get("sku", "")) if variant.get("sku") is not None else None
                available_stock_raw = variant.get("available_stock")
                reserved_stock_raw = variant.get("reserved_stock")

                available_stock = _safe_int(available_stock_raw, default=0)
                reserved_stock = _safe_int(reserved_stock_raw, default=0)

                variant_problem_messages: list[str] = []
                if "available_stock" not in variant:
                    variant_problem_messages.append("available_stock missing")
                if "reserved_stock" not in variant:
                    variant_problem_messages.append("reserved_stock missing")
                if available_stock < 0:
                    variant_problem_messages.append("available_stock negative")
                if reserved_stock < 0:
                    variant_problem_messages.append("reserved_stock negative")

                if variant_problem_messages:
                    has_issue = True
                    variant_issues += 1
                    if len(samples) < sample_limit:
                        samples.append(
                            {
                                "product_id": product_id,
                                "index": idx,
                                "sku": sku,
                                "issue": ", ".join(variant_problem_messages),
                            }
                        )

                if apply_fixes:
                    normalized_available = max(0, available_stock)
                    normalized_reserved = max(0, reserved_stock)

                    normalized_variant = dict(variant)
                    normalized_variant["available_stock"] = normalized_available
                    normalized_variant["reserved_stock"] = normalized_reserved

                    if normalized_variant != variant:
                        product_fixed_variant_count += 1

                    updated_variants.append(normalized_variant)
                else:
                    updated_variants.append(variant)

            if has_issue:
                products_with_issues += 1

            if apply_fixes and product_fixed_variant_count > 0:
                result = await products.update_one(
                    {"_id": product.get("_id")},
                    {"$set": {"variants": updated_variants}},
                )
                if result.modified_count > 0:
                    fixed_products += 1
                    fixed_variants += product_fixed_variant_count

        print("\n=== Inventory Invariant Reconciliation ===")
        print(f"Database: {database_name}")
        print(f"Products scanned: {total_products}")
        print(f"Products with issues: {products_with_issues}")
        print(f"Variants with issues: {variant_issues}")

        if apply_fixes:
            print(f"Products fixed: {fixed_products}")
            print(f"Variants fixed: {fixed_variants}")
        else:
            print("Fix mode: OFF (read-only)")

        if samples:
            print("\nSample issues:")
            for sample in samples:
                print(
                    f"- product_id={sample['product_id']} index={sample['index']} "
                    f"sku={sample['sku']} issue={sample['issue']}"
                )
        else:
            print("\nNo inventory invariant issues detected.")

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        reconcile_inventory_invariants(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            sample_limit=max(args.sample_limit, 1),
            apply_fixes=args.apply_fixes,
        )
    )
