import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict

from beanie import init_beanie
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.core.config import settings
from app.models.category_model import Category
from app.models.product_model import Product
from app.models.product_variant_model import ProductVariant


BRANDS_BY_PARENT: dict[str, list[str]] = {
    "Electronics": ["Sony", "Samsung", "Apple", "Lenovo", "Canon", "Asus"],
    "Fashion": ["Levis", "Zara", "H&M", "Puma", "Nike", "Adidas"],
    "Home and Kitchen": ["Ikea", "Philips", "Prestige", "Hawkins", "Milton"],
    "Beauty and Personal Care": ["Loreal", "Maybelline", "Nivea", "Minimalist", "Cetaphil"],
    "Sports and Outdoors": ["Decathlon", "Yonex", "Nivia", "Coleman", "Wildcraft"],
    "Books": ["Penguin", "HarperCollins", "Scholastic", "Oxford", "Cambridge"],
    "Toys and Games": ["Lego", "Mattel", "Hasbro", "Funskool", "Skillmatics"],
    "Automotive": ["Bosch", "3M", "Castrol", "Shell", "Mobil"],
    "Health": ["Himalaya", "Dabur", "MuscleBlaze", "Revital", "GNC"],
    "Grocery": ["Tata", "Aashirvaad", "Kelloggs", "Nestle", "Quaker"],
    "Pet Supplies": ["Pedigree", "Royal Canin", "Whiskas", "Drools", "MeO"],
    "Jewelry": ["Tanishq", "CaratLane", "Kalyan", "Sukkhi", "Giva"],
    "Watches": ["Casio", "Titan", "Fossil", "Timex", "Amazfit"],
    "Office Supplies": ["Classmate", "Cello", "HP", "Canon", "Epson"],
    "Baby Products": ["Pampers", "Johnsons", "Mee Mee", "Huggies", "Chicco"],
    "Garden": ["Ugaoo", "TrustBasket", "Bosch", "KraftSeeds", "Rico"],
    "Music": ["Yamaha", "Fender", "Casio", "Roland", "Korg"],
    "Gaming": ["Razer", "Logitech", "Sony", "Microsoft", "Corsair"],
    "Travel": ["American Tourister", "Skybags", "VIP", "Safari", "Wildcraft"],
    "Art and Craft": ["Camel", "Faber-Castell", "Pidilite", "Brustro", "Fevicryl"],
}


SPEC_TEMPLATES_BY_SUBCATEGORY: dict[str, Dict[str, str]] = {
    "Smartphones": {"Display": "6.5 inch AMOLED", "Battery": "5000 mAh", "Network": "5G"},
    "Laptops": {"Processor": "Intel Core i7", "RAM": "16 GB", "Storage": "512 GB SSD"},
    "Cameras": {"Sensor": "24 MP APS-C", "Video": "4K", "Stabilization": "Optical"},
    "Men Clothing": {"Fabric": "Cotton Blend", "Fit": "Regular", "Wash": "Machine Wash"},
    "Women Clothing": {"Fabric": "Viscose", "Fit": "Comfort", "Care": "Hand/Machine Wash"},
    "Footwear": {"Upper": "Synthetic", "Sole": "Rubber", "Closure": "Lace-Up"},
    "Cookware": {"Material": "Hard Anodized", "Compatibility": "Gas and Induction", "Coating": "Non-stick"},
    "Furniture": {"Material": "Engineered Wood", "Assembly": "DIY", "Finish": "Matte"},
    "Home Decor": {"Material": "Resin", "Theme": "Modern", "Use": "Indoor"},
    "Smart Watches": {"Display": "AMOLED", "Battery": "7 days", "Features": "Heart Rate + SpO2"},
    "Consoles": {"Storage": "1 TB", "Resolution": "4K", "Controller": "Wireless"},
    "PC Gaming": {"GPU": "RTX 4060", "RAM": "16 GB", "Refresh Rate": "165 Hz"},
    "Luggage": {"Capacity": "65 L", "Material": "Polycarbonate", "Wheels": "360 Spinner"},
    "Painting": {"Medium": "Acrylic", "Surface": "Canvas", "Set Size": "24 Pieces"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed products mapped to existing subcategories."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=120,
        help="Number of products to seed (minimum 100 recommended). Default: 120",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview records without inserting into the database.",
    )
    parser.add_argument(
        "--enrich-existing",
        action="store_true",
        help="Update existing seeded products with realistic brands, specs, and images.",
    )
    return parser.parse_args()


def token(value: str, max_len: int = 6) -> str:
    cleaned = "".join(ch for ch in value.upper() if ch.isalnum())
    return (cleaned[:max_len] or "GEN").ljust(3, "X")


def build_product_name(subcategory_name: str, round_no: int) -> str:
    return f"{subcategory_name} Product {round_no}"


def pick_brand(parent_name: str, subcategory_name: str, round_no: int) -> str:
    options = BRANDS_BY_PARENT.get(parent_name, ["Generic"])
    idx = (len(subcategory_name) + round_no) % len(options)
    return options[idx]


def build_description(parent_name: str, subcategory_name: str, round_no: int, brand: str) -> str:
    return (
        f"{brand} {subcategory_name.lower()} from our {parent_name} range. "
        f"Edition {round_no} balances quality, comfort, and long-term reliability for everyday use."
    )


def build_specifications(parent_name: str, subcategory_name: str, round_no: int) -> Dict[str, str]:
    specs = {
        "Category": parent_name,
        "Subcategory": subcategory_name,
        "Edition": f"v{round_no}",
        "Warranty": "12 months",
    }
    specs.update(SPEC_TEMPLATES_BY_SUBCATEGORY.get(subcategory_name, {"Material": "Premium Composite", "Usage": "Daily"}))
    return specs


def build_image_urls(parent_name: str, subcategory_name: str, round_no: int) -> list[str]:
    seed_base = f"{token(parent_name)}-{token(subcategory_name)}-{round_no:03d}".lower()
    return [
        f"https://picsum.photos/seed/{seed_base}-1/900/900",
        f"https://picsum.photos/seed/{seed_base}-2/900/900",
    ]


def build_variants(parent_name: str, subcategory_name: str, round_no: int) -> list[ProductVariant]:
    prefix = f"SEED-{token(parent_name)}-{token(subcategory_name)}-{round_no:03d}"

    price_bias = {
        "Electronics": 8000,
        "Gaming": 9500,
        "Watches": 5000,
        "Jewelry": 7000,
        "Fashion": 1200,
        "Books": 350,
        "Grocery": 180,
    }
    std_price = price_bias.get(parent_name, 1500) + (round_no * 25)
    pro_price = std_price + 220

    return [
        ProductVariant(
            sku=f"{prefix}-S",
            price=std_price,
            discount_price=std_price - 80,
            available_stock=15 + (round_no % 20),
            attributes={"tier": "Standard", "finish": "Matte"},
        ),
        ProductVariant(
            sku=f"{prefix}-P",
            price=pro_price,
            discount_price=pro_price - 120,
            available_stock=8 + (round_no % 15),
            attributes={"tier": "Pro", "finish": "Glossy"},
        ),
    ]


async def plan_seed_items(count: int) -> list[tuple[Category, int]]:
    subcategories = await Category.find(Category.parent_id != None).to_list()  # noqa: E711
    if not subcategories:
        raise SystemExit("No subcategories found. Seed categories first.")

    # Stable ordering gives deterministic names/SKUs for idempotency.
    subcategories.sort(key=lambda c: (str(c.parent_id), c.name.lower()))

    planned: list[tuple[Category, int]] = []
    round_no = 1
    while len(planned) < count:
        for subcategory in subcategories:
            if len(planned) >= count:
                break
            planned.append((subcategory, round_no))
        round_no += 1

    return planned


async def seed_products(count: int, dry_run: bool = False, enrich_existing: bool = False) -> None:
    if count < 100:
        raise SystemExit("Please provide --count >= 100 for this task.")

    await init_beanie(
        connection_string=f"{settings.MONGODB_URL}/{settings.DATABASE_NAME}",
        document_models=[Category, Product],
    )

    planned_items = await plan_seed_items(count)

    created = 0
    updated = 0
    skipped = 0

    parent_cache: dict[str, str] = {}

    for subcategory, round_no in planned_items:
        if subcategory.id is None:
            skipped += 1
            continue

        subcategory_id = subcategory.id

        parent_name = "General"
        if subcategory.parent_id is not None:
            parent_id_str = str(subcategory.parent_id)
            if parent_id_str in parent_cache:
                parent_name = parent_cache[parent_id_str]
            else:
                parent = await Category.get(subcategory.parent_id)
                if parent:
                    parent_name = parent.name
                parent_cache[parent_id_str] = parent_name

        product_name = build_product_name(subcategory.name, round_no)
        brand = pick_brand(parent_name, subcategory.name, round_no)
        description = build_description(parent_name, subcategory.name, round_no, brand)
        specifications = build_specifications(parent_name, subcategory.name, round_no)
        images = build_image_urls(parent_name, subcategory.name, round_no)
        variants = build_variants(parent_name, subcategory.name, round_no)

        existing = await Product.find_one(
            Product.name == product_name,
            Product.category_id == subcategory_id,
        )
        if existing:
            if enrich_existing and not dry_run:
                existing.description = description
                existing.brand = brand
                existing.variants = variants
                existing.images = images
                existing.specifications = specifications
                existing.rating = min(5.0, 3.8 + (round_no % 10) * 0.1)
                existing.num_reviews = 20 + round_no * 3
                existing.is_available = True
                existing.is_featured = (round_no % 5 == 0)
                await existing.save()
                updated += 1
                continue
            skipped += 1
            continue

        if dry_run:
            created += 1
            continue

        product = Product(
            name=product_name,
            description=description,
            brand=brand,
            category_id=subcategory_id,
            variants=variants,
            images=images,
            rating=min(5.0, 3.8 + (round_no % 10) * 0.1),
            num_reviews=20 + round_no * 3,
            specifications=specifications,
            is_available=True,
            is_featured=(round_no % 5 == 0),
        )

        await product.insert()
        created += 1

    mode = "Dry run" if dry_run else "Completed"
    print(f"{mode}: target products={count}")
    print(f"Inserted products: {created}")
    print(f"Updated existing: {updated}")
    print(f"Skipped existing: {skipped}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed_products(count=args.count, dry_run=args.dry_run, enrich_existing=args.enrich_existing))
