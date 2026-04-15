import argparse
import asyncio
import os
import sys
from pathlib import Path

from bson import ObjectId
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
        description="Backfill missing is_verified in users and optionally verify selected users."
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
        help="How many sample users to print in dry-run mode.",
    )
    parser.add_argument(
        "--verify-email",
        action="append",
        default=[],
        help="Email(s) to mark verified. Can be passed multiple times and supports comma-separated values.",
    )
    parser.add_argument(
        "--verify-username",
        action="append",
        default=[],
        help="Username(s) to mark verified. Can be passed multiple times and supports comma-separated values.",
    )
    parser.add_argument(
        "--verify-user-id",
        action="append",
        default=[],
        help="Mongo ObjectId(s) to mark verified. Can be passed multiple times and supports comma-separated values.",
    )
    parser.add_argument(
        "--verify-count",
        type=int,
        default=0,
        help="Additionally mark first N currently unverified users as verified.",
    )
    return parser.parse_args()


def split_csv_values(values: list[str]) -> list[str]:
    parsed: list[str] = []
    for raw in values:
        for value in raw.split(","):
            clean = value.strip()
            if clean:
                parsed.append(clean)
    return parsed


def normalize_emails(values: list[str]) -> list[str]:
    return [value.strip().lower() for value in values if value.strip()]


def parse_object_ids(values: list[str]) -> list[ObjectId]:
    parsed_ids: list[ObjectId] = []
    for value in values:
        try:
            parsed_ids.append(ObjectId(value.strip()))
        except Exception as exc:
            raise SystemExit(f"Invalid --verify-user-id value '{value}': {exc}") from exc
    return parsed_ids


def build_missing_verified_filter() -> dict:
    return {
        "$or": [
            {"is_verified": {"$exists": False}},
            {"is_verified": None},
        ]
    }


def build_explicit_verify_filter(emails: list[str], usernames: list[str], user_ids: list[ObjectId]) -> dict | None:
    clauses: list[dict] = []
    if emails:
        clauses.append({"email": {"$in": emails}})
    if usernames:
        clauses.append({"user_name": {"$in": usernames}})
    if user_ids:
        clauses.append({"_id": {"$in": user_ids}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


async def print_sample(cursor, label: str) -> None:
    print(label)
    async for doc in cursor:
        print(
            f"- _id={doc.get('_id')} user_name={doc.get('user_name')} "
            f"email={doc.get('email')} is_verified={doc.get('is_verified')}"
        )


async def migrate_users(
    mongodb_url: str,
    database_name: str,
    dry_run: bool,
    sample_size: int,
    verify_emails: list[str],
    verify_usernames: list[str],
    verify_user_ids: list[ObjectId],
    verify_count: int,
) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    database = client[database_name]
    users = database[USERS_COLLECTION]

    missing_verified_filter = build_missing_verified_filter()
    explicit_verify_filter = build_explicit_verify_filter(verify_emails, verify_usernames, verify_user_ids)

    try:
        total_users = await users.count_documents({})
        missing_verified_count = await users.count_documents(missing_verified_filter)

        print(f"Database: {database_name}")
        print(f"Collection: {USERS_COLLECTION}")
        print(f"Total users: {total_users}")
        print(f"Users missing is_verified: {missing_verified_count}")

        explicit_ids: list[ObjectId] = []
        explicit_to_verify_count = 0
        if explicit_verify_filter is not None:
            explicit_docs = await users.find(explicit_verify_filter, {"_id": 1, "is_verified": 1}).to_list(length=None)
            explicit_ids = [doc["_id"] for doc in explicit_docs]
            explicit_to_verify_count = sum(1 for doc in explicit_docs if doc.get("is_verified") is not True)
            print(f"Explicit user matches: {len(explicit_ids)}")
            print(f"Explicit users needing verify=true: {explicit_to_verify_count}")

        additional_candidate_filter: dict = {
            "is_verified": {"$ne": True}
        }
        if explicit_ids:
            additional_candidate_filter = {
                "$and": [
                    {"is_verified": {"$ne": True}},
                    {"_id": {"$nin": explicit_ids}},
                ]
            }

        additional_docs = []
        if verify_count > 0:
            additional_docs = await users.find(
                additional_candidate_filter,
                {"_id": 1, "user_name": 1, "email": 1, "is_verified": 1},
            ).sort("_id", 1).limit(verify_count).to_list(length=verify_count)
            print(f"Additional users selected by --verify-count: {len(additional_docs)}")

        if dry_run:
            if missing_verified_count > 0:
                missing_sample_cursor = users.find(
                    missing_verified_filter,
                    {"_id": 1, "user_name": 1, "email": 1, "is_verified": 1},
                ).limit(max(sample_size, 0))
                await print_sample(missing_sample_cursor, "Dry run sample: users missing is_verified")

            if explicit_verify_filter is not None and explicit_ids:
                explicit_sample_cursor = users.find(
                    {"_id": {"$in": explicit_ids}},
                    {"_id": 1, "user_name": 1, "email": 1, "is_verified": 1},
                ).limit(max(sample_size, 0))
                await print_sample(explicit_sample_cursor, "Dry run sample: explicit users to verify")

            if additional_docs:
                print("Dry run sample: additional users selected by --verify-count")
                for doc in additional_docs[: max(sample_size, 0)]:
                    print(
                        f"- _id={doc.get('_id')} user_name={doc.get('user_name')} "
                        f"email={doc.get('email')} is_verified={doc.get('is_verified')}"
                    )

            print("No changes were written.")
            return

        backfill_result = await users.update_many(
            missing_verified_filter,
            {"$set": {"is_verified": False}},
        )
        print(f"Backfilled is_verified=false for users: {backfill_result.modified_count}")

        explicit_verified_modified = 0
        if explicit_ids:
            explicit_verify_result = await users.update_many(
                {
                    "_id": {"$in": explicit_ids},
                    "is_verified": {"$ne": True},
                },
                {"$set": {"is_verified": True}},
            )
            explicit_verified_modified = explicit_verify_result.modified_count
        print(f"Explicit users updated to is_verified=true: {explicit_verified_modified}")

        additional_verified_modified = 0
        if additional_docs:
            additional_ids = [doc["_id"] for doc in additional_docs]
            additional_verify_result = await users.update_many(
                {
                    "_id": {"$in": additional_ids},
                    "is_verified": {"$ne": True},
                },
                {"$set": {"is_verified": True}},
            )
            additional_verified_modified = additional_verify_result.modified_count
        print(f"Additional users updated to is_verified=true: {additional_verified_modified}")

        final_missing_verified_count = await users.count_documents(missing_verified_filter)
        print(f"Users still missing is_verified after migration: {final_missing_verified_count}")
        print("Migration complete.")

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()

    verify_emails = normalize_emails(split_csv_values(args.verify_email))
    verify_usernames = split_csv_values(args.verify_username)
    verify_user_ids = parse_object_ids(split_csv_values(args.verify_user_id))

    asyncio.run(
        migrate_users(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            dry_run=args.dry_run,
            sample_size=args.sample_size,
            verify_emails=verify_emails,
            verify_usernames=verify_usernames,
            verify_user_ids=verify_user_ids,
            verify_count=max(args.verify_count, 0),
        )
    )
