import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MONGODB_URL = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "e_commerce"
CARTS_COLLECTION = "carts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing version field in carts for optimistic locking compatibility."
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
        help="Show what would be changed without writing updates.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10,
        help="How many sample cart ids to print in dry-run mode.",
    )
    parser.add_argument(
        "--backfill-updated-at",
        action="store_true",
        help="Also set updated_at=now for matched carts if updated_at is missing or null.",
    )
    return parser.parse_args()


def build_missing_version_filter() -> dict:
    return {
        "$or": [
            {"version": {"$exists": False}},
            {"version": None},
        ]
    }


async def migrate_carts(
    mongodb_url: str,
    database_name: str,
    dry_run: bool,
    sample_size: int,
    backfill_updated_at: bool,
) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    database = client[database_name]
    carts = database[CARTS_COLLECTION]

    missing_version_filter = build_missing_version_filter()

    try:
        total_carts = await carts.count_documents({})
        missing_version_count = await carts.count_documents(missing_version_filter)

        print(f"Database: {database_name}")
        print(f"Collection: {CARTS_COLLECTION}")
        print(f"Total carts: {total_carts}")
        print(f"Carts missing version: {missing_version_count}")

        if missing_version_count == 0:
            print("No migration needed. All carts already have version.")
            return

        if dry_run:
            projection = {"_id": 1, "user_id": 1, "version": 1, "updated_at": 1}
            cursor = carts.find(missing_version_filter, projection).limit(max(sample_size, 0))

            print("Dry run mode: sample carts that would be updated:")
            async for doc in cursor:
                print(
                    f"- _id={doc.get('_id')} user_id={doc.get('user_id')} "
                    f"version={doc.get('version')} updated_at={doc.get('updated_at')}"
                )
            print("No changes were written.")
            return

        update_doc = {"$set": {"version": 1}}

        if backfill_updated_at:
            now_utc = datetime.now(timezone.utc)
            update_doc["$set"]["updated_at"] = now_utc

        result = await carts.update_many(missing_version_filter, update_doc)

        print(f"Matched carts: {result.matched_count}")
        print(f"Modified carts: {result.modified_count}")
        print("Migration complete.")

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        migrate_carts(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            dry_run=args.dry_run,
            sample_size=args.sample_size,
            backfill_updated_at=args.backfill_updated_at,
        )
    )
