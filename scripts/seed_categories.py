import argparse
import asyncio
import sys
from pathlib import Path

from beanie import init_beanie
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.core.config import settings
from app.models.category_model import Category


CATEGORY_TREE: dict[str, list[str]] = {
    "Electronics": ["Smartphones", "Laptops", "Cameras"],
    "Fashion": ["Men Clothing", "Women Clothing", "Footwear"],
    "Home and Kitchen": ["Cookware", "Furniture", "Home Decor"],
    "Beauty and Personal Care": ["Skincare", "Haircare", "Makeup"],
    "Sports and Outdoors": ["Fitness Equipment", "Camping Gear", "Cycling"],
    "Books": ["Fiction", "Non Fiction", "Children Books"],
    "Toys and Games": ["Board Games", "Action Figures", "Educational Toys"],
    "Automotive": ["Car Accessories", "Motorcycle Parts", "Tools and Equipment"],
    "Health": ["Supplements", "Medical Supplies", "Wellness"],
    "Grocery": ["Beverages", "Snacks", "Organic Food"],
    "Pet Supplies": ["Dog Supplies", "Cat Supplies", "Aquarium"],
    "Jewelry": ["Necklaces", "Rings", "Bracelets"],
    "Watches": ["Men Watches", "Women Watches", "Smart Watches"],
    "Office Supplies": ["Stationery", "Office Furniture", "Printers"],
    "Baby Products": ["Diapers", "Baby Clothing", "Feeding"],
    "Garden": ["Plants", "Garden Tools", "Outdoor Decor"],
    "Music": ["Instruments", "Audio Accessories", "Vinyl Records"],
    "Gaming": ["Consoles", "PC Gaming", "Gaming Accessories"],
    "Travel": ["Luggage", "Travel Accessories", "Backpacks"],
    "Art and Craft": ["Painting", "Craft Supplies", "Drawing"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed at least 20 parent categories and 3 subcategories per parent."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be inserted without writing to the database.",
    )
    return parser.parse_args()


async def get_or_create_category(name: str, parent_id=None, dry_run: bool = False) -> tuple[Category | None, bool]:
    existing = await Category.find_one(Category.name == name, Category.parent_id == parent_id)
    if existing:
        return existing, False

    if dry_run:
        return None, True

    category = Category(name=name, parent_id=parent_id)
    created = await category.insert()
    return created, True


async def seed_categories(dry_run: bool = False) -> None:
    await init_beanie(
        connection_string=f"{settings.MONGODB_URL}/{settings.DATABASE_NAME}",
        document_models=[Category],
    )

    created_parents = 0
    created_children = 0
    skipped = 0

    for parent_name, subcategories in CATEGORY_TREE.items():
        parent, parent_created = await get_or_create_category(parent_name, None, dry_run=dry_run)

        if parent_created:
            created_parents += 1
        else:
            skipped += 1

        parent_id = parent.id if parent else None
        for child_name in subcategories:
            _, child_created = await get_or_create_category(child_name, parent_id, dry_run=dry_run)
            if child_created:
                created_children += 1
            else:
                skipped += 1

    total_parents = len(CATEGORY_TREE)
    total_children = sum(len(children) for children in CATEGORY_TREE.values())

    mode = "Dry run" if dry_run else "Completed"
    print(f"{mode}: parent categories target={total_parents}, subcategories target={total_children}.")
    print(f"Inserted parent categories: {created_parents}")
    print(f"Inserted subcategories: {created_children}")
    print(f"Skipped existing: {skipped}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed_categories(dry_run=args.dry_run))