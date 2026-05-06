from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, MutableMapping

from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.core.config import settings


DEFAULT_ADDRESS_LANGUAGE = "en"
MISSING_ADDRESS_LANGUAGE_QUERY = {
    "$or": [
        {"addresses.language": {"$exists": False}},
        {"addresses": {"$elemMatch": {"language": {"$exists": False}}}},
    ]
}


@dataclass(frozen=True)
class BackfillResult:
    users_updated: int = 0
    addresses_updated: int = 0


def _address_with_default_language(address: Any) -> tuple[Any, bool]:
    if not isinstance(address, MutableMapping):
        return address, False
    if "language" in address:
        return address, False

    updated_address = dict(address)
    updated_address["language"] = DEFAULT_ADDRESS_LANGUAGE
    return updated_address, True


def backfill_address_language(users_collection) -> BackfillResult:
    users_updated = 0
    addresses_updated = 0

    for user in users_collection.find(MISSING_ADDRESS_LANGUAGE_QUERY):
        addresses = user.get("addresses")
        if not addresses or not isinstance(addresses, list):
            continue

        updated_addresses = []
        changed = False
        for address in addresses:
            updated_address, address_changed = _address_with_default_language(address)
            updated_addresses.append(updated_address)
            if address_changed:
                changed = True
                addresses_updated += 1

        if not changed:
            continue

        users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"addresses": updated_addresses}},
        )
        users_updated += 1

    return BackfillResult(users_updated=users_updated, addresses_updated=addresses_updated)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill saved user address language metadata for legacy MongoDB documents."
    )
    parser.add_argument("--mongodb-url", default=os.getenv("MONGODB_URL", settings.MONGODB_URL))
    parser.add_argument("--database", default=os.getenv("DATABASE_NAME", settings.DATABASE_NAME))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = MongoClient(args.mongodb_url, tz_aware=True)
    try:
        result = backfill_address_language(client[args.database]["users"])
    finally:
        client.close()

    print(f"Users updated: {result.users_updated}")
    print(f"Addresses updated: {result.addresses_updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
