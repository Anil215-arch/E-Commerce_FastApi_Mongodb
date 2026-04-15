import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MONGODB_URL = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "e_commerce"

AUDIT_COLLECTIONS = ["users", "categories", "products", "orders"]
AUDIT_FIELDS = ["created_at", "updated_at", "is_deleted", "created_by", "updated_by", "deleted_at", "deleted_by"]

DEFAULT_ADDRESS = {
    "full_name": "Unknown User",
    "phone_number": "0000000000",
    "street_address": "Unknown street",
    "city": "NA",
    "postal_code": "0000",
    "state": "NA",
    "country": "NA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill MongoDB documents to align with current app models."
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
        "--dry-run",
        action="store_true",
        help="Preview counts without writing updates.",
    )
    parser.add_argument(
        "--drop-legacy-order-total-amount",
        action="store_true",
        help="Unset legacy orders.total_amount after mapping it to new fields.",
    )
    return parser.parse_args()


def missing_or_null_filter(field_name: str) -> dict:
    return {
        "$or": [
            {field_name: {"$exists": False}},
            {field_name: None},
        ]
    }


def missing_any_fields_filter(field_names: list[str]) -> dict:
    clauses = []
    for field_name in field_names:
        clauses.extend([
            {field_name: {"$exists": False}},
            {field_name: None},
        ])
    return {"$or": clauses}


async def count_filter(collection, query: dict) -> int:
    return await collection.count_documents(query)


async def migrate(
    mongodb_url: str,
    database_name: str,
    dry_run: bool,
    drop_legacy_order_total_amount: bool,
) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]

    try:
        print(f"Database: {database_name}")

        # 1) AuditDocument field backfill across users/categories/products/orders
        print("\n[1/4] Audit field backfill")
        audit_missing_filter = missing_any_fields_filter(AUDIT_FIELDS)
        for collection_name in AUDIT_COLLECTIONS:
            collection = db[collection_name]
            affected = await count_filter(collection, audit_missing_filter)
            print(f"- {collection_name}: documents missing audit fields = {affected}")

            if dry_run or affected == 0:
                continue

            result = await collection.update_many(
                {},
                [
                    {
                        "$set": {
                            "created_at": {"$ifNull": ["$created_at", {"$toDate": "$_id"}]},
                            "updated_at": {
                                "$ifNull": [
                                    "$updated_at",
                                    {"$ifNull": ["$created_at", {"$toDate": "$_id"}]},
                                ]
                            },
                            "is_deleted": {"$ifNull": ["$is_deleted", False]},
                            "created_by": {"$ifNull": ["$created_by", None]},
                            "updated_by": {"$ifNull": ["$updated_by", None]},
                            "deleted_at": {"$ifNull": ["$deleted_at", None]},
                            "deleted_by": {"$ifNull": ["$deleted_by", None]},
                        }
                    }
                ],
            )
            print(f"  matched={result.matched_count} modified={result.modified_count}")

        # 2) User model specific fields
        print("\n[2/4] User-specific field backfill")
        users = db["users"]
        users_missing_addresses = await count_filter(users, missing_or_null_filter("addresses"))
        print(f"- users missing addresses = {users_missing_addresses}")

        if not dry_run and users_missing_addresses > 0:
            result = await users.update_many(
                missing_or_null_filter("addresses"),
                {"$set": {"addresses": []}},
            )
            print(f"  matched={result.matched_count} modified={result.modified_count}")

        # 3) Order model upgrade from legacy total_amount shape
        print("\n[3/4] Order shape upgrade")
        orders = db["orders"]
        order_required_new_fields = [
            "shipping_address",
            "billing_address",
            "subtotal",
            "tax_amount",
            "shipping_fee",
            "grand_total",
        ]
        orders_missing_new_shape = await count_filter(orders, missing_any_fields_filter(order_required_new_fields))
        orders_with_legacy_total = await count_filter(orders, {"total_amount": {"$exists": True}})

        print(f"- orders missing new required fields = {orders_missing_new_shape}")
        print(f"- orders with legacy total_amount = {orders_with_legacy_total}")

        if not dry_run and (orders_missing_new_shape > 0 or orders_with_legacy_total > 0):
            result = await orders.update_many(
                {},
                [
                    {
                        "$set": {
                            "shipping_address": {"$ifNull": ["$shipping_address", DEFAULT_ADDRESS]},
                            "billing_address": {"$ifNull": ["$billing_address", DEFAULT_ADDRESS]},
                            "subtotal": {"$ifNull": ["$subtotal", {"$ifNull": ["$total_amount", 0]}]},
                            "tax_amount": {"$ifNull": ["$tax_amount", 0]},
                            "shipping_fee": {"$ifNull": ["$shipping_fee", 0]},
                            "grand_total": {"$ifNull": ["$grand_total", {"$ifNull": ["$total_amount", 0]}]},
                        }
                    }
                ],
            )
            print(f"  matched={result.matched_count} modified={result.modified_count}")

        # 4) Optional legacy field cleanup
        print("\n[4/4] Optional cleanup")
        if drop_legacy_order_total_amount:
            remaining_legacy_total = await count_filter(orders, {"total_amount": {"$exists": True}})
            print(f"- legacy orders.total_amount remaining before cleanup = {remaining_legacy_total}")

            if not dry_run and remaining_legacy_total > 0:
                result = await orders.update_many(
                    {"total_amount": {"$exists": True}},
                    {"$unset": {"total_amount": ""}},
                )
                print(f"  matched={result.matched_count} modified={result.modified_count}")
        else:
            print("- cleanup skipped (use --drop-legacy-order-total-amount to enable)")

        print("\nDone.")
        if dry_run:
            print("Dry run mode: no changes written.")

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        migrate(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            dry_run=args.dry_run,
            drop_legacy_order_total_amount=args.drop_legacy_order_total_amount,
        )
    )
