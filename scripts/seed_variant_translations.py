import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from beanie import init_beanie
from dotenv import load_dotenv
from pymongo.errors import ServerSelectionTimeoutError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.core.config import settings
from app.models.product_model import Product
from app.models.product_variant_model import ProductVariantTranslation


VALUE_TRANSLATIONS = {
    "Standard": {"hi": "स्टैंडर्ड", "ja": "標準"},
    "Pro": {"hi": "प्रो", "ja": "プロ"},
    "Matte": {"hi": "मैट", "ja": "マット"},
    "Glossy": {"hi": "ग्लॉसी", "ja": "光沢"},
}

TARGET_LANGUAGES = ("hi", "ja")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill variant attribute translations (hi, ja) for existing products."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report changes without writing to MongoDB.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing variant translations for hi/ja.",
    )
    return parser.parse_args()


def _translated_attributes(source_attributes: dict[str, str], language: str) -> dict[str, str]:
    translated: dict[str, str] = {}
    for key, value in source_attributes.items():
        value_str = str(value)
        translated_value = VALUE_TRANSLATIONS.get(value_str, {}).get(language, value_str)
        translated[str(key)] = translated_value
    return translated


async def run_backfill(*, dry_run: bool, overwrite: bool) -> dict[str, int]:
    async def _init_with_url(mongo_url: str) -> None:
        await init_beanie(
            connection_string=f"{mongo_url}/{settings.DATABASE_NAME}",
            document_models=[Product],
        )

    configured_mongo_url = settings.MONGODB_URL
    try:
        await _init_with_url(configured_mongo_url)
    except ServerSelectionTimeoutError:
        parsed = urlsplit(configured_mongo_url)
        host = parsed.hostname
        if host != "mongodb":
            raise

        fallback_netloc = parsed.netloc.replace("mongodb", "localhost", 1)
        fallback_url = urlunsplit((parsed.scheme, fallback_netloc, parsed.path, parsed.query, parsed.fragment))
        await _init_with_url(fallback_url)

    summary = {
        "products_scanned": 0,
        "products_updated": 0,
        "variants_scanned": 0,
        "variants_updated": 0,
        "skipped_existing": 0,
    }

    products = await Product.find(Product.is_deleted != True).to_list()

    for product in products:
        summary["products_scanned"] += 1
        product_changed = False

        for variant in product.variants:
            summary["variants_scanned"] += 1
            variant_changed = False

            if variant.translations is None:
                variant.translations = {}

            for language in TARGET_LANGUAGES:
                existing_translation = variant.translations.get(language)

                if existing_translation is not None and not overwrite:
                    summary["skipped_existing"] += 1
                    continue

                translated_attrs = _translated_attributes(variant.attributes, language)
                new_translation = ProductVariantTranslation(attributes=translated_attrs)

                if existing_translation is None or existing_translation.attributes != new_translation.attributes:
                    variant.translations[language] = new_translation
                    variant_changed = True

            if variant_changed:
                summary["variants_updated"] += 1
                product_changed = True

        if product_changed:
            summary["products_updated"] += 1
            if not dry_run:
                await product.save()

    return summary


def print_summary(summary: dict[str, int], dry_run: bool, overwrite: bool) -> None:
    print(f"mode: {'dry-run' if dry_run else 'write'}")
    print(f"overwrite: {overwrite}")
    print(f"products_scanned: {summary['products_scanned']}")
    print(f"products_updated: {summary['products_updated']}")
    print(f"variants_scanned: {summary['variants_scanned']}")
    print(f"variants_updated: {summary['variants_updated']}")
    print(f"skipped_existing: {summary['skipped_existing']}")


def main() -> int:
    args = parse_args()
    summary = asyncio.run(run_backfill(dry_run=args.dry_run, overwrite=args.overwrite))
    print_summary(summary, dry_run=args.dry_run, overwrite=args.overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())