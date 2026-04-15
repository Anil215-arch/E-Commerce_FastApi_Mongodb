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
USERS_COLLECTION = "users"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing is_deleted in users for soft-delete compatible queries."
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
        help="Preview changes without writing updates.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10,
        help="How many sample user records to print in dry-run mode.",
    )
    parser.add_argument(
        "--backfill-delete-audit",
        action="store_true",
        help="Also set deleted_at=None and deleted_by=None when those fields are missing.",
    )
    return parser.parse_args()


def build_missing_is_deleted_filter() -> dict:
    return {
        "$or": [
            {"is_deleted": {"$exists": False}},
            {"is_deleted": None},
        ]
    }


async def migrate_users(
    mongodb_url: str,
    database_name: str,
    dry_run: bool,
    sample_size: int,
    backfill_delete_audit: bool,
) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    database = client[database_name]
    users = database[USERS_COLLECTION]

    missing_is_deleted_filter = build_missing_is_deleted_filter()

    try:
        total_users = await users.count_documents({})
        missing_is_deleted_count = await users.count_documents(missing_is_deleted_filter)

        print(f"Database: {database_name}")
        print(f"Collection: {USERS_COLLECTION}")
        print(f"Total users: {total_users}")
        print(f"Users missing is_deleted: {missing_is_deleted_count}")

        if missing_is_deleted_count == 0:
            print("No migration needed. All users already have is_deleted.")
            return

        if dry_run:
            projection = {
                "_id": 1,
                "user_name": 1,
                "email": 1,
                "is_deleted": 1,
                "deleted_at": 1,
                "deleted_by": 1,
            }
            cursor = users.find(missing_is_deleted_filter, projection).limit(max(sample_size, 0))

            print("Dry run mode: sample users that would be updated:")
            async for doc in cursor:
                print(
                    f"- _id={doc.get('_id')} user_name={doc.get('user_name')} "
                    f"email={doc.get('email')} is_deleted={doc.get('is_deleted')} "
                    f"deleted_at={doc.get('deleted_at')} deleted_by={doc.get('deleted_by')}"
                )
            print("No changes were written.")
            return

        set_fields = {"is_deleted": False}
        if backfill_delete_audit:
            set_fields.update({"deleted_at": None, "deleted_by": None})

        result = await users.update_many(missing_is_deleted_filter, {"$set": set_fields})

        print(f"Matched users: {result.matched_count}")
        print(f"Modified users: {result.modified_count}")

        remaining_missing = await users.count_documents(missing_is_deleted_filter)
        print(f"Users still missing is_deleted after migration: {remaining_missing}")
        print("Migration complete.")

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        migrate_users(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            dry_run=args.dry_run,
            sample_size=max(args.sample_size, 0),
            backfill_delete_audit=args.backfill_delete_audit,
        )
    )
