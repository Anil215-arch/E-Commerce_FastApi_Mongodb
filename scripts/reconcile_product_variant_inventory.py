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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and optionally repair product variant inventory invariants "
            "(available_stock/reserved_stock)."
        )
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
        help="Repair missing or negative inventory fields by normalizing them to non-negative values.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=25,
        help="How many violating variants to print. Default: 25",
    )
    return parser.parse_args()


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_non_negative(value: Any) -> int:
    casted = _as_int(value)
    if casted is None:
        return 0
    return max(0, casted)


def _variant_sku(raw_variant: Any, index: int) -> str:
    if isinstance(raw_variant, dict):
        sku = raw_variant.get("sku")
        if isinstance(sku, str) and sku.strip():
            return sku.strip()
    return f"<missing-sku:{index}>"


def inspect_variant(raw_variant: Any, index: int) -> tuple[list[str], dict[str, Any] | None]:
    issues: list[str] = []

    if not isinstance(raw_variant, dict):
        issues.append("variant is not an object")
        repaired = {
            "sku": f"REPAIRED-SKU-{index}",
            "price": 1,
            "discount_price": None,
            "available_stock": 0,
            "reserved_stock": 0,
            "attributes": {},
        }
        return issues, repaired

    repaired = dict(raw_variant)

    available_stock = raw_variant.get("available_stock")
    reserved_stock = raw_variant.get("reserved_stock")

    if "available_stock" not in raw_variant:
        issues.append("missing available_stock")
        if "stock" in raw_variant:
            repaired["available_stock"] = _normalize_non_negative(raw_variant.get("stock"))
        else:
            repaired["available_stock"] = 0
    else:
        normalized_available = _normalize_non_negative(available_stock)
        if _as_int(available_stock) is None:
            issues.append("available_stock is not an integer")
        elif normalized_available != int(available_stock):
            issues.append("available_stock is negative")
        repaired["available_stock"] = normalized_available

    if "reserved_stock" not in raw_variant:
        issues.append("missing reserved_stock")
        repaired["reserved_stock"] = 0
    else:
        normalized_reserved = _normalize_non_negative(reserved_stock)
        if _as_int(reserved_stock) is None:
            issues.append("reserved_stock is not an integer")
        elif normalized_reserved != int(reserved_stock):
            issues.append("reserved_stock is negative")
        repaired["reserved_stock"] = normalized_reserved

    return issues, repaired


async def scan_products(products_collection) -> tuple[list[dict[str, Any]], list[UpdateOne]]:
    findings: list[dict[str, Any]] = []
    repair_ops: list[UpdateOne] = []

    async for product in products_collection.find({}, {"variants": 1}):
        product_id = product.get("_id")
        raw_variants = product.get("variants")
        if not isinstance(raw_variants, list):
            findings.append(
                {
                    "product_id": str(product_id),
                    "sku": "<variants>",
                    "issues": ["variants is not a list"],
                }
            )
            repair_ops.append(
                UpdateOne(
                    {"_id": product_id},
                    {"$set": {"variants": []}},
                )
            )
            continue

        normalized_variants: list[dict[str, Any] | Any] = []
        product_has_repairs = False

        for index, raw_variant in enumerate(raw_variants):
            issues, repaired = inspect_variant(raw_variant, index)
            if issues:
                findings.append(
                    {
                        "product_id": str(product_id),
                        "sku": _variant_sku(raw_variant, index),
                        "issues": issues,
                    }
                )
                product_has_repairs = True

            normalized_variants.append(repaired if repaired is not None else raw_variant)

        if product_has_repairs:
            repair_ops.append(
                UpdateOne(
                    {"_id": product_id},
                    {"$set": {"variants": normalized_variants}},
                )
            )

    return findings, repair_ops


def print_findings(findings: list[dict[str, Any]], sample_limit: int) -> None:
    print(f"Violating variants found: {len(findings)}")
    if not findings:
        return

    print("Sample violations:")
    for finding in findings[:sample_limit]:
        issue_text = "; ".join(finding["issues"])
        print(
            f"- product_id={finding['product_id']} "
            f"sku={finding['sku']} issues={issue_text}"
        )

    remaining = len(findings) - min(len(findings), sample_limit)
    if remaining > 0:
        print(f"... and {remaining} more")


async def reconcile(
    mongodb_url: str,
    database_name: str,
    apply: bool,
    sample_limit: int,
) -> int:
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    products = db["products"]

    try:
        print(f"Database: {database_name}")
        findings, repair_ops = await scan_products(products)
        print_findings(findings, sample_limit)

        if not apply:
            if findings:
                print("Dry run only. Re-run with --apply to normalize fixable violations.")
                return 1
            print("No inventory invariant violations found.")
            return 0

        if repair_ops:
            result = await products.bulk_write(repair_ops, ordered=False)
            print(
                "Applied repairs: "
                f"matched={result.matched_count} modified={result.modified_count}"
            )
        else:
            print("No repairs needed.")

        post_apply_findings, _ = await scan_products(products)
        print_findings(post_apply_findings, sample_limit)
        if post_apply_findings:
            print("Inventory invariant violations remain after apply.")
            return 1

        print("Inventory invariants are clean after apply.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(
        reconcile(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            apply=args.apply,
            sample_limit=max(1, args.sample_limit),
        )
    )
    raise SystemExit(exit_code)
