import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.models.base_model import AuditDocument
from app.models.cart_model import Cart
from app.models.category_model import Category
from app.models.email_otp_model import EmailOTPVerification
from app.models.order_model import Order
from app.models.product_model import Product
from app.models.revoked_token_model import RevokedToken
from app.models.transaction_model import Transaction
from app.models.user_model import User
from app.schemas.category_schema import CategoryResponse
from app.schemas.order_schema import OrderResponse
from app.schemas.user_schema import UserResponse

DEFAULT_MONGODB_URL = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "e_commerce"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    collection: str
    model: type


@dataclass(frozen=True)
class SchemaSpec:
    name: str
    collection: str
    schema: type


MODEL_SPECS: list[ModelSpec] = [
    ModelSpec("User", "users", User),
    ModelSpec("Category", "categories", Category),
    ModelSpec("Product", "products", Product),
    ModelSpec("Cart", "carts", Cart),
    ModelSpec("Order", "orders", Order),
    ModelSpec("Transaction", "transactions", Transaction),
    ModelSpec("EmailOTPVerification", "email_otp_verifications", EmailOTPVerification),
    ModelSpec("RevokedToken", "revoked_tokens", RevokedToken),
]

SCHEMA_SPECS: list[SchemaSpec] = [
    SchemaSpec("UserResponse", "users", UserResponse),
    SchemaSpec("CategoryResponse", "categories", CategoryResponse),
    SchemaSpec("OrderResponse", "orders", OrderResponse),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit MongoDB documents against app models and selected schemas."
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
        "--sample-errors",
        type=int,
        default=5,
        help="How many validation error examples to print per model/schema.",
    )
    return parser.parse_args()


def model_expected_fields(model: type) -> list[str]:
    excluded = {"id", "revision_id"}
    return [name for name in model.model_fields.keys() if name not in excluded]


def enum_or_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def compact_error(error: dict[str, Any]) -> str:
    loc = ".".join(str(p) for p in error.get("loc", []))
    msg = error.get("msg", "")
    typ = error.get("type", "")
    return f"loc={loc} type={typ} msg={msg}"


async def audit_model_collection(db, spec: ModelSpec, sample_errors: int) -> dict[str, Any]:
    collection = db[spec.collection]
    expected_fields = model_expected_fields(spec.model)

    total = 0
    missing_field_counter: Counter[str] = Counter()
    null_field_counter: Counter[str] = Counter()
    extra_field_counter: Counter[str] = Counter()
    validation_error_counter: Counter[str] = Counter()
    validation_error_examples: list[dict[str, Any]] = []

    cursor = collection.find({}, None)
    async for doc in cursor:
        total += 1
        doc_keys = set(doc.keys())

        for field_name in expected_fields:
            if field_name not in doc_keys:
                missing_field_counter[field_name] += 1
            elif doc.get(field_name) is None:
                null_field_counter[field_name] += 1

        allowed_doc_keys = set(expected_fields) | {"_id"}
        for extra in doc_keys - allowed_doc_keys:
            extra_field_counter[extra] += 1

        try:
            spec.model.model_validate(doc)
        except ValidationError as exc:
            for err in exc.errors():
                validation_error_counter[compact_error(err)] += 1
            if len(validation_error_examples) < sample_errors:
                validation_error_examples.append(
                    {
                        "_id": str(doc.get("_id")),
                        "errors": [compact_error(e) for e in exc.errors()],
                    }
                )

    result = {
        "name": spec.name,
        "collection": spec.collection,
        "total_documents": total,
        "missing_fields": dict(sorted(missing_field_counter.items(), key=lambda x: (-x[1], x[0]))),
        "null_fields": dict(sorted(null_field_counter.items(), key=lambda x: (-x[1], x[0]))),
        "extra_fields": dict(sorted(extra_field_counter.items(), key=lambda x: (-x[1], x[0]))),
        "validation_errors": dict(sorted(validation_error_counter.items(), key=lambda x: (-x[1], x[0]))),
        "validation_error_examples": validation_error_examples,
        "inherits_audit_document": issubclass(spec.model, AuditDocument),
    }
    return result


async def audit_schema_collection(db, spec: SchemaSpec, sample_errors: int) -> dict[str, Any]:
    collection = db[spec.collection]

    total = 0
    schema_error_counter: Counter[str] = Counter()
    schema_error_examples: list[dict[str, Any]] = []

    cursor = collection.find({}, None)
    async for doc in cursor:
        total += 1
        try:
            spec.schema.model_validate(doc)
        except ValidationError as exc:
            for err in exc.errors():
                schema_error_counter[compact_error(err)] += 1
            if len(schema_error_examples) < sample_errors:
                schema_error_examples.append(
                    {
                        "_id": str(doc.get("_id")),
                        "errors": [compact_error(e) for e in exc.errors()],
                    }
                )

    return {
        "name": spec.name,
        "collection": spec.collection,
        "total_documents": total,
        "validation_errors": dict(sorted(schema_error_counter.items(), key=lambda x: (-x[1], x[0]))),
        "validation_error_examples": schema_error_examples,
    }


def print_section_header(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def print_top_counts(label: str, values: dict[str, int], limit: int = 10) -> None:
    if not values:
        print(f"{label}: none")
        return
    print(f"{label}:")
    for idx, (key, count) in enumerate(values.items()):
        if idx >= limit:
            print(f"  ... and {len(values) - limit} more")
            break
        print(f"  - {key}: {count}")


async def run_audit(mongodb_url: str, database_name: str, sample_errors: int) -> None:
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]

    try:
        await init_beanie(
            connection_string=f"{mongodb_url}/{database_name}",
            document_models=[spec.model for spec in MODEL_SPECS],
        )

        print_section_header("Database Audit Summary")
        print(f"Database: {database_name}")

        model_results: list[dict[str, Any]] = []
        for spec in MODEL_SPECS:
            model_results.append(await audit_model_collection(db, spec, sample_errors))

        schema_results: list[dict[str, Any]] = []
        for spec in SCHEMA_SPECS:
            schema_results.append(await audit_schema_collection(db, spec, sample_errors))

        print_section_header("Model Alignment")
        for result in model_results:
            print(
                f"Model {result['name']} on collection {result['collection']} "
                f"(documents={result['total_documents']})"
            )
            print_top_counts("Missing fields", result["missing_fields"])
            print_top_counts("Null fields", result["null_fields"])
            print_top_counts("Extra fields", result["extra_fields"])
            print_top_counts("Validation errors", result["validation_errors"])
            if result["validation_error_examples"]:
                print("Validation error examples:")
                for example in result["validation_error_examples"]:
                    print(f"  - _id={example['_id']}")
                    for err in example["errors"]:
                        print(f"    * {err}")
            print("-" * 88)

        print_section_header("Schema Compatibility")
        for result in schema_results:
            print(
                f"Schema {result['name']} on collection {result['collection']} "
                f"(documents={result['total_documents']})"
            )
            print_top_counts("Validation errors", result["validation_errors"])
            if result["validation_error_examples"]:
                print("Validation error examples:")
                for example in result["validation_error_examples"]:
                    print(f"  - _id={example['_id']}")
                    for err in example["errors"]:
                        print(f"    * {err}")
            print("-" * 88)

        print_section_header("Actionable Drift Patterns")
        drift_map: dict[str, int] = defaultdict(int)
        for result in model_results:
            collection = result["collection"]
            for field_name, count in result["missing_fields"].items():
                if count > 0:
                    drift_map[f"{collection}: missing field {field_name}"] += count

        if not drift_map:
            print("No field drift detected against document models.")
        else:
            for key, count in sorted(drift_map.items(), key=lambda x: (-x[1], x[0])):
                print(f"- {key} (documents affected: {count})")

    finally:
        client.close()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        run_audit(
            mongodb_url=args.mongodb_url,
            database_name=args.database_name,
            sample_errors=max(args.sample_errors, 1),
        )
    )
