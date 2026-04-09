import argparse
import asyncio
import sys
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
        description="Rename 'starting_price' field to 'price' in MongoDB products collection."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many documents would change without writing updates.",
    )
    return parser.parse_args()


async def migrate_starting_price_to_price(dry_run: bool) -> None:
    """
    Migrate all products by renaming 'starting_price' field to 'price'.
    This also recalculates the price based on minimum variant price.
    """
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.DATABASE_NAME]
    collection = database["products"]

    processed_count = 0
    changed_count = 0

    try:
        # Find all documents that have starting_price field
        cursor = collection.find({"starting_price": {"$exists": True}})
        
        async for document in cursor:
            processed_count += 1
            doc_id = document["_id"]
            old_price = document.get("starting_price", 0)

            # Recalculate price based on minimum variant price
            variants = document.get("variants", [])
            prices = [v.get("price") for v in variants if isinstance(v.get("price"), int)]
            new_price = min(prices, default=0)

            if dry_run:
                print(
                    f"Would migrate product {doc_id}: "
                    f"rename starting_price ({old_price}) -> price ({new_price})"
                )
                changed_count += 1
                continue

            # First rename the field
            await collection.update_one(
                {"_id": doc_id},
                {"$rename": {"starting_price": "price"}},
            )
            
            # Then update the value if it changed
            if new_price != old_price:
                await collection.update_one(
                    {"_id": doc_id},
                    {"$set": {"price": new_price}},
                )
            
            changed_count += 1
            print(f"✓ Migrated product {doc_id}: price = {new_price}")

        # Also update the index: remove old index and create new one if it exists
        if not dry_run:
            try:
                # Drop old index if it exists
                await collection.drop_index("starting_price_1__id_1")
                print("✓ Dropped old index on starting_price")
            except Exception as e:
                # Index might not exist, that's okay
                if "index not found" not in str(e):
                    print(f"Note: Could not drop old index: {e}")

            try:
                # Create new index on price field
                await collection.create_index([("price", 1), ("_id", 1)])
                print("✓ Created new index on price")
            except Exception as e:
                print(f"Note: Index might already exist: {e}")

    except Exception as e:
        print(f"Error during migration: {e}", file=sys.stderr)
        return
    finally:
        client.close()

    # Print summary
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Documents processed: {processed_count}")
    print(f"Documents changed: {changed_count}")
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes were made to the database")
        print("Run without --dry-run to apply the migration")
    else:
        print("\n✅ Migration completed successfully!")
    print("=" * 60)


async def main():
    args = parse_args()
    await migrate_starting_price_to_price(args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
