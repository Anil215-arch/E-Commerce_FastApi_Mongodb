import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

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
    parser.add_argument(
        "--drop-legacy-product-rating",
        action="store_true",
        help="Unset legacy products.rating after mapping to aggregate rating fields.",
    )
    parser.add_argument(
        "--migrate-legacy-user-wishlist",
        action="store_true",
        help="Migrate users.wishlist (embedded) entries to wishlists collection when entries contain both product_id and sku.",
    )
    parser.add_argument(
        "--drop-legacy-user-wishlist",
        action="store_true",
        help="Unset users.wishlist after optional migration.",
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
    drop_legacy_product_rating: bool,
    migrate_legacy_user_wishlist: bool,
    drop_legacy_user_wishlist: bool,
) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]

    try:
        print(f"Database: {database_name}")

        # 1) AuditDocument field backfill across users/categories/products/orders
        print("\n[1/6] Audit field backfill")
        audit_missing_filter = missing_any_fields_filter(AUDIT_FIELDS)
        for collection_name in [*AUDIT_COLLECTIONS, "wishlists"]:
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
        print("\n[2/6] User-specific field backfill")
        users = db["users"]
        users_missing_addresses = await count_filter(users, missing_or_null_filter("addresses"))
        print(f"- users missing addresses = {users_missing_addresses}")

        if not dry_run and users_missing_addresses > 0:
            result = await users.update_many(
                missing_or_null_filter("addresses"),
                {"$set": {"addresses": []}},
            )
            print(f"  matched={result.matched_count} modified={result.modified_count}")

        # 3) Optional migration for legacy users.wishlist -> wishlists collection
        print("\n[3/6] Legacy users.wishlist migration (optional)")
        wishlists = db["wishlists"]
        users_with_legacy_wishlist = await count_filter(users, {"wishlist": {"$exists": True, "$ne": []}})
        users_with_wishlist_field = await count_filter(users, {"wishlist": {"$exists": True}})
        print(f"- users with legacy wishlist data = {users_with_legacy_wishlist}")

        migrated_rows = 0
        skipped_rows = 0
        if not dry_run and migrate_legacy_user_wishlist and users_with_legacy_wishlist > 0:
            async for user in users.find({"wishlist": {"$exists": True, "$ne": []}}, {"wishlist": 1}):
                user_id = user.get("_id")
                entries = user.get("wishlist") or []
                for entry in entries:
                    if not isinstance(entry, dict):
                        skipped_rows += 1
                        continue

                    product_id = entry.get("product_id")
                    sku = entry.get("sku")
                    if not product_id or not sku:
                        skipped_rows += 1
                        continue

                    await wishlists.update_one(
                        {
                            "user_id": user_id,
                            "product_id": product_id,
                            "sku": sku,
                        },
                        {
                            "$setOnInsert": {
                                "created_by": user_id,
                                "updated_by": user_id,
                                "is_deleted": False,
                            },
                            "$set": {
                                "updated_by": user_id,
                            },
                        },
                        upsert=True,
                    )
                    migrated_rows += 1

            print(f"  migrated rows={migrated_rows} skipped rows={skipped_rows}")
        elif migrate_legacy_user_wishlist:
            print("  no legacy rows to migrate")
        else:
            print("- migration skipped (use --migrate-legacy-user-wishlist to enable)")

        if not dry_run and drop_legacy_user_wishlist and users_with_wishlist_field > 0:
            result = await users.update_many(
                {"wishlist": {"$exists": True}},
                {"$unset": {"wishlist": ""}},
            )
            print(f"  dropped users.wishlist matched={result.matched_count} modified={result.modified_count}")
        elif drop_legacy_user_wishlist:
            print("  no users.wishlist field found for cleanup")
        else:
            print("- cleanup skipped (use --drop-legacy-user-wishlist to enable)")

        # 4) Order model upgrade from legacy total_amount shape
        print("\n[4/6] Order shape upgrade")
        orders = db["orders"]
        order_required_new_fields = [
            "shipping_address",
            "billing_address",
            "subtotal",
            "tax_amount",
            "shipping_fee",
            "grand_total",
            "cancellation_reason",
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
                            "cancellation_reason": {"$ifNull": ["$cancellation_reason", None]},
                        }
                    }
                ],
            )
            print(f"  matched={result.matched_count} modified={result.modified_count}")

        # 5) Product rating model drift migration
        print("\n[5/6] Product rating aggregate backfill")
        products = db["products"]
        reviews = db["reviews"]

        products_missing_rating_shape_filter = {
            "$or": [
                {"average_rating": {"$exists": False}},
                {"average_rating": None},
                {"rating_sum": {"$exists": False}},
                {"rating_sum": None},
                {"rating_breakdown": {"$exists": False}},
                {"rating_breakdown": None},
            ]
        }
        products_missing_rating_shape = await count_filter(products, products_missing_rating_shape_filter)
        products_with_legacy_rating = await count_filter(products, {"rating": {"$exists": True}})
        active_reviews = await count_filter(reviews, {"is_deleted": {"$ne": True}})

        print(f"- products missing aggregate rating fields = {products_missing_rating_shape}")
        print(f"- products with legacy rating field = {products_with_legacy_rating}")
        print(f"- active reviews available for exact backfill = {active_reviews}")

        if not dry_run and active_reviews > 0:
            stats_cursor = reviews.aggregate(
                [
                    {"$match": {"is_deleted": {"$ne": True}}},
                    {
                        "$group": {
                            "_id": "$product_id",
                            "num_reviews": {"$sum": 1},
                            "rating_sum": {"$sum": "$rating"},
                            "one": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$rating", 1]}, 1, 0]
                                }
                            },
                            "two": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$rating", 2]}, 1, 0]
                                }
                            },
                            "three": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$rating", 3]}, 1, 0]
                                }
                            },
                            "four": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$rating", 4]}, 1, 0]
                                }
                            },
                            "five": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$rating", 5]}, 1, 0]
                                }
                            },
                        }
                    },
                ]
            )

            ops: list[UpdateOne] = []
            async for stat in stats_cursor:
                count = int(stat.get("num_reviews", 0))
                score_sum = int(stat.get("rating_sum", 0))
                avg = round(score_sum / count, 2) if count > 0 else 0.0

                ops.append(
                    UpdateOne(
                        {"_id": stat["_id"]},
                        {
                            "$set": {
                                "num_reviews": count,
                                "rating_sum": score_sum,
                                "average_rating": avg,
                                "rating_breakdown": {
                                    "1": int(stat.get("one", 0)),
                                    "2": int(stat.get("two", 0)),
                                    "3": int(stat.get("three", 0)),
                                    "4": int(stat.get("four", 0)),
                                    "5": int(stat.get("five", 0)),
                                },
                            }
                        },
                    )
                )

            if ops:
                bulk_result = await products.bulk_write(ops, ordered=False)
                print(
                    "  applied exact review-based aggregates: "
                    f"matched={bulk_result.matched_count} modified={bulk_result.modified_count}"
                )

        if not dry_run and products_missing_rating_shape > 0:
            result = await products.update_many(
                products_missing_rating_shape_filter,
                [
                    {
                        "$set": {
                            "num_reviews": {"$ifNull": ["$num_reviews", 0]},
                            "_legacy_rating": {"$ifNull": ["$rating", 0]},
                            "_legacy_num_reviews": {"$ifNull": ["$num_reviews", 0]},
                        }
                    },
                    {
                        "$set": {
                            "_legacy_bucket": {
                                "$min": [
                                    5,
                                    {
                                        "$max": [
                                            1,
                                            {
                                                "$toInt": {
                                                    "$round": ["$_legacy_rating", 0]
                                                }
                                            },
                                        ]
                                    },
                                ]
                            },
                            "rating_sum": {
                                "$ifNull": [
                                    "$rating_sum",
                                    {
                                        "$toInt": {
                                            "$round": [
                                                {
                                                    "$multiply": [
                                                        "$_legacy_rating",
                                                        "$_legacy_num_reviews",
                                                    ]
                                                },
                                                0,
                                            ]
                                        }
                                    },
                                ]
                            },
                        }
                    },
                    {
                        "$set": {
                            "average_rating": {
                                "$ifNull": [
                                    "$average_rating",
                                    {
                                        "$cond": [
                                            {"$gt": ["$num_reviews", 0]},
                                            "$_legacy_rating",
                                            0.0,
                                        ]
                                    },
                                ]
                            },
                            "rating_breakdown": {
                                "$ifNull": [
                                    "$rating_breakdown",
                                    {
                                        "1": {
                                            "$cond": [
                                                {"$eq": ["$_legacy_bucket", 1]},
                                                "$_legacy_num_reviews",
                                                0,
                                            ]
                                        },
                                        "2": {
                                            "$cond": [
                                                {"$eq": ["$_legacy_bucket", 2]},
                                                "$_legacy_num_reviews",
                                                0,
                                            ]
                                        },
                                        "3": {
                                            "$cond": [
                                                {"$eq": ["$_legacy_bucket", 3]},
                                                "$_legacy_num_reviews",
                                                0,
                                            ]
                                        },
                                        "4": {
                                            "$cond": [
                                                {"$eq": ["$_legacy_bucket", 4]},
                                                "$_legacy_num_reviews",
                                                0,
                                            ]
                                        },
                                        "5": {
                                            "$cond": [
                                                {"$eq": ["$_legacy_bucket", 5]},
                                                "$_legacy_num_reviews",
                                                0,
                                            ]
                                        },
                                    },
                                ]
                            },
                        }
                    },
                    {"$unset": ["_legacy_rating", "_legacy_num_reviews", "_legacy_bucket"]},
                ],
            )
            print(f"  fallback aggregate backfill matched={result.matched_count} modified={result.modified_count}")

        # 6) Optional legacy field cleanup
        print("\n[6/6] Optional cleanup")
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

        if drop_legacy_product_rating:
            remaining_legacy_rating = await count_filter(products, {"rating": {"$exists": True}})
            print(f"- legacy products.rating remaining before cleanup = {remaining_legacy_rating}")

            if not dry_run and remaining_legacy_rating > 0:
                result = await products.update_many(
                    {"rating": {"$exists": True}},
                    {"$unset": {"rating": ""}},
                )
                print(f"  matched={result.matched_count} modified={result.modified_count}")
        else:
            print("- cleanup skipped (use --drop-legacy-product-rating to enable)")

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
            drop_legacy_product_rating=args.drop_legacy_product_rating,
            migrate_legacy_user_wishlist=args.migrate_legacy_user_wishlist,
            drop_legacy_user_wishlist=args.drop_legacy_user_wishlist,
        )
    )
