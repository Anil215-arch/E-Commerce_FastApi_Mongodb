import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MONGODB_URL = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "e_commerce"

AUDIT_COLLECTIONS = ["users", "categories", "products", "orders", "transactions"]

REALISTIC_ADDRESS_TEMPLATES = [
    {
        "street_address": "24 MG Road, Residency Block",
        "city": "Bengaluru",
        "postal_code": "560001",
        "state": "Karnataka",
        "country": "India",
    },
    {
        "street_address": "55 Park Street, Sector 17",
        "city": "Gurugram",
        "postal_code": "122001",
        "state": "Haryana",
        "country": "India",
    },
    {
        "street_address": "12 Bandra Link Road",
        "city": "Mumbai",
        "postal_code": "400050",
        "state": "Maharashtra",
        "country": "India",
    },
    {
        "street_address": "88 Anna Salai",
        "city": "Chennai",
        "postal_code": "600002",
        "state": "Tamil Nadu",
        "country": "India",
    },
    {
        "street_address": "41 Salt Lake Sector V",
        "city": "Kolkata",
        "postal_code": "700091",
        "state": "West Bengal",
        "country": "India",
    },
    {
        "street_address": "9 Banjara Hills Road No. 3",
        "city": "Hyderabad",
        "postal_code": "500034",
        "state": "Telangana",
        "country": "India",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill realistic audit metadata and profile data for null/empty values."
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
    return parser.parse_args()


def audit_missing_filter() -> dict[str, Any]:
    return {
        "$or": [
            {"created_by": None},
            {"updated_by": None},
            {"created_by": {"$exists": False}},
            {"updated_by": {"$exists": False}},
        ]
    }


async def resolve_primary_actor_id(users_collection) -> ObjectId:
    super_admin = await users_collection.find_one(
        {"role": "super_admin", "is_deleted": False},
        {"_id": 1},
    )
    if super_admin:
        return super_admin["_id"]

    admin = await users_collection.find_one(
        {"role": "admin", "is_deleted": False},
        {"_id": 1},
    )
    if admin:
        return admin["_id"]

    any_user = await users_collection.find_one({}, {"_id": 1})
    if any_user:
        return any_user["_id"]

    raise SystemExit("No users found in database. Seed users first.")


async def backfill_users_audit(users_collection, primary_actor_id: ObjectId, dry_run: bool) -> None:
    created_filter = {"$or": [{"created_by": None}, {"created_by": {"$exists": False}}]}
    updated_filter = {"$or": [{"updated_by": None}, {"updated_by": {"$exists": False}}]}

    missing_created = await users_collection.count_documents(created_filter)
    missing_updated = await users_collection.count_documents(updated_filter)

    print(f"- users missing created_by = {missing_created}")
    print(f"- users missing updated_by = {missing_updated}")

    if dry_run:
        return

    if missing_created > 0:
        created_result = await users_collection.update_many(
            created_filter,
            [
                {
                    "$set": {
                        "created_by": {
                            "$cond": [
                                {"$eq": ["$role", "super_admin"]},
                                "$_id",
                                primary_actor_id,
                            ]
                        }
                    }
                }
            ],
        )
        print(
            "  users created_by backfill: "
            f"matched={created_result.matched_count} modified={created_result.modified_count}"
        )

    if missing_updated > 0:
        updated_result = await users_collection.update_many(
            updated_filter,
            [{"$set": {"updated_by": {"$ifNull": ["$created_by", primary_actor_id]}}}],
        )
        print(
            "  users updated_by backfill: "
            f"matched={updated_result.matched_count} modified={updated_result.modified_count}"
        )


async def backfill_collection_audit(collection, collection_name: str, primary_actor_id: ObjectId, dry_run: bool) -> None:
    created_filter = {"$or": [{"created_by": None}, {"created_by": {"$exists": False}}]}
    updated_filter = {"$or": [{"updated_by": None}, {"updated_by": {"$exists": False}}]}

    missing_created = await collection.count_documents(created_filter)
    missing_updated = await collection.count_documents(updated_filter)

    print(f"- {collection_name} missing created_by = {missing_created}")
    print(f"- {collection_name} missing updated_by = {missing_updated}")

    if dry_run:
        return

    if collection_name == "orders":
        if missing_created > 0:
            created_result = await collection.update_many(
                created_filter,
                [{"$set": {"created_by": {"$ifNull": ["$user_id", primary_actor_id]}}}],
            )
            print(
                f"  {collection_name} created_by backfill: "
                f"matched={created_result.matched_count} modified={created_result.modified_count}"
            )

        if missing_updated > 0:
            updated_result = await collection.update_many(
                updated_filter,
                [
                    {
                        "$set": {
                            "updated_by": {
                                "$ifNull": ["$updated_by", {"$ifNull": ["$created_by", {"$ifNull": ["$user_id", primary_actor_id]}]}]
                            }
                        }
                    }
                ],
            )
            print(
                f"  {collection_name} updated_by backfill: "
                f"matched={updated_result.matched_count} modified={updated_result.modified_count}"
            )
    else:
        if missing_created > 0:
            created_result = await collection.update_many(
                created_filter,
                {"$set": {"created_by": primary_actor_id}},
            )
            print(
                f"  {collection_name} created_by backfill: "
                f"matched={created_result.matched_count} modified={created_result.modified_count}"
            )

        if missing_updated > 0:
            updated_result = await collection.update_many(
                updated_filter,
                [{"$set": {"updated_by": {"$ifNull": ["$created_by", primary_actor_id]}}}],
            )
            print(
                f"  {collection_name} updated_by backfill: "
                f"matched={updated_result.matched_count} modified={updated_result.modified_count}"
            )


async def backfill_transactions_audit(transactions_collection, orders_collection, primary_actor_id: ObjectId, dry_run: bool) -> None:
    created_filter = {"$or": [{"created_by": None}, {"created_by": {"$exists": False}}]}
    updated_filter = {"$or": [{"updated_by": None}, {"updated_by": {"$exists": False}}]}
    pending_filter = {
        "$or": [
            {"created_by": None},
            {"updated_by": None},
            {"created_by": {"$exists": False}},
            {"updated_by": {"$exists": False}},
        ]
    }

    missing_created = await transactions_collection.count_documents(created_filter)
    missing_updated = await transactions_collection.count_documents(updated_filter)

    print(f"- transactions missing created_by = {missing_created}")
    print(f"- transactions missing updated_by = {missing_updated}")

    target_rows = await transactions_collection.find(
        pending_filter,
        {"_id": 1, "order_id": 1, "created_by": 1, "updated_by": 1},
    ).to_list(length=None)

    print(f"- transactions needing ownership backfill = {len(target_rows)}")

    if dry_run or not target_rows:
        return

    modified = 0
    for tx_doc in target_rows:
        order_doc = None
        order_id = tx_doc.get("order_id")
        if order_id is not None:
            order_doc = await orders_collection.find_one(
                {"_id": order_id},
                {"user_id": 1, "created_by": 1, "updated_by": 1},
            )

        base_actor = primary_actor_id
        if order_doc:
            base_actor = (
                order_doc.get("updated_by")
                or order_doc.get("created_by")
                or order_doc.get("user_id")
                or primary_actor_id
            )

        created_by_value = tx_doc.get("created_by") or base_actor
        updated_by_value = tx_doc.get("updated_by") or created_by_value

        result = await transactions_collection.update_one(
            {"_id": tx_doc["_id"]},
            {
                "$set": {
                    "created_by": created_by_value,
                    "updated_by": updated_by_value,
                }
            },
        )
        modified += result.modified_count

    print(f"  transactions ownership backfill: matched={len(target_rows)} modified={modified}")


async def backfill_deleted_metadata(collection, collection_name: str, primary_actor_id: ObjectId, dry_run: bool) -> None:
    deleted_filter = {
        "is_deleted": True,
        "$or": [
            {"deleted_at": None},
            {"deleted_by": None},
            {"deleted_at": {"$exists": False}},
            {"deleted_by": {"$exists": False}},
        ],
    }

    affected = await collection.count_documents(deleted_filter)
    print(f"- {collection_name} deleted records missing metadata = {affected}")

    if dry_run or affected == 0:
        return

    result = await collection.update_many(
        deleted_filter,
        [
            {
                "$set": {
                    "deleted_at": {
                        "$ifNull": [
                            "$deleted_at",
                            {
                                "$ifNull": [
                                    "$updated_at",
                                    {"$ifNull": ["$created_at", {"$toDate": "$_id"}]},
                                ]
                            },
                        ]
                    },
                    "deleted_by": {
                        "$ifNull": [
                            "$deleted_by",
                            {"$ifNull": ["$updated_by", {"$ifNull": ["$created_by", primary_actor_id]}]},
                        ]
                    },
                }
            }
        ],
    )
    print(f"  {collection_name} deleted metadata backfill: matched={result.matched_count} modified={result.modified_count}")


def build_address(user_doc: dict[str, Any], idx: int) -> dict[str, str]:
    template = REALISTIC_ADDRESS_TEMPLATES[idx % len(REALISTIC_ADDRESS_TEMPLATES)]
    full_name = str(user_doc.get("user_name") or "Customer").strip()
    phone_number = str(user_doc.get("mobile") or "9000000000").strip()
    return {
        "full_name": full_name,
        "phone_number": phone_number,
        "street_address": template["street_address"],
        "city": template["city"],
        "postal_code": template["postal_code"],
        "state": template["state"],
        "country": template["country"],
    }


async def backfill_user_addresses(users_collection, dry_run: bool) -> None:
    empty_address_filter = {
        "$or": [
            {"addresses": {"$exists": False}},
            {"addresses": None},
            {"addresses": []},
        ]
    }

    target_users = await users_collection.find(
        empty_address_filter,
        {"_id": 1, "user_name": 1, "mobile": 1},
    ).to_list(length=None)

    print(f"- users with empty addresses = {len(target_users)}")

    if dry_run or not target_users:
        return

    modified = 0
    for idx, user_doc in enumerate(target_users):
        address = build_address(user_doc, idx)
        result = await users_collection.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"addresses": [address]}},
        )
        modified += result.modified_count

    print(f"  users address backfill: matched={len(target_users)} modified={modified}")


async def run_backfill(mongodb_url: str, database_name: str, dry_run: bool) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]

    try:
        print(f"Database: {database_name}")

        users = db["users"]
        primary_actor_id = await resolve_primary_actor_id(users)
        print(f"Primary actor user_id for audit backfill: {primary_actor_id}")

        print("\n[1/3] Audit ownership fields (created_by, updated_by)")
        await backfill_users_audit(users, primary_actor_id, dry_run)
        for collection_name in ["categories", "products", "orders"]:
            await backfill_collection_audit(db[collection_name], collection_name, primary_actor_id, dry_run)
        await backfill_transactions_audit(
            transactions_collection=db["transactions"],
            orders_collection=db["orders"],
            primary_actor_id=primary_actor_id,
            dry_run=dry_run,
        )

        print("\n[2/3] Deleted metadata for soft-deleted records only")
        for collection_name in AUDIT_COLLECTIONS:
            await backfill_deleted_metadata(db[collection_name], collection_name, primary_actor_id, dry_run)

        print("\n[3/3] User profile enrichment")
        await backfill_user_addresses(users, dry_run)

        print("\nDone.")
        if dry_run:
            print("Dry run mode: no changes written.")

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        run_backfill(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            dry_run=args.dry_run,
        )
    )