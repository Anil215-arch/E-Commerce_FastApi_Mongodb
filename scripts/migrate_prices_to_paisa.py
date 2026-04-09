import argparse
import asyncio
import os
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.core.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert product prices stored in float rupees to integer paisa in MongoDB."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many documents would change without writing updates.",
    )
    return parser.parse_args()


def is_float_like(value) -> bool:
    return isinstance(value, (float, Decimal))


def to_paisa(value):
    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if not is_float_like(value):
        return value

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value

    return int((decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def convert_variant(variant: dict) -> tuple[dict, bool]:
    updated_variant = dict(variant)
    changed = False

    for field_name in ("price", "discount_price"):
        if field_name in updated_variant:
            converted_value = to_paisa(updated_variant[field_name])
            if converted_value != updated_variant[field_name]:
                updated_variant[field_name] = converted_value
                changed = True

    return updated_variant, changed


def recalculate_price(variants: list[dict]) -> int:
    prices = [variant.get("price") for variant in variants if isinstance(variant.get("price"), int)]
    return min(prices, default=0)


async def migrate_prices_to_paisa(dry_run: bool) -> None:
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.DATABASE_NAME]
    collection = database["products"]

    processed_count = 0
    changed_count = 0

    try:
        cursor = collection.find({}, {"variants": 1, "price": 1})
        async for document in cursor:
            processed_count += 1

            variants = document.get("variants") or []
            updated_variants = []
            document_changed = False

            for variant in variants:
                updated_variant, variant_changed = convert_variant(variant)
                updated_variants.append(updated_variant)
                document_changed = document_changed or variant_changed

            updated_price = recalculate_price(updated_variants)
            if updated_price != document.get("price", 0):
                document_changed = True

            if not document_changed:
                continue

            changed_count += 1

            if dry_run:
                print(
                    f"Would update product {document['_id']}: "
                    f"price {document.get('price', 0)} -> {updated_price}"
                )
                continue

            await collection.update_one(
                {"_id": document["_id"]},
                {
                    "$set": {
                        "variants": updated_variants,
                        "price": updated_price,
                    }
                },
            )

        action = "would be updated" if dry_run else "updated"
        print(f"Processed {processed_count} products; {changed_count} {action}.")
    finally:
        client.close()


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(migrate_prices_to_paisa(arguments.dry_run))