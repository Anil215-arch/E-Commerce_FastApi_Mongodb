import os

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


load_dotenv()


def _get_db() -> tuple[MongoClient, str]:
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DATABASE_NAME", "e_commerce")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=1500)
    return client, db_name


@pytest.fixture
def mongo_db():
    client, db_name = _get_db()
    try:
        client.admin.command("ping")
    except PyMongoError:
        client.close()
        pytest.skip("MongoDB is not reachable for DB alignment smoke test")

    db = client[db_name]
    try:
        yield db
    finally:
        client.close()


def test_products_rating_fields_aligned_with_current_model(mongo_db):
    products = mongo_db["products"]

    missing_new_fields = products.count_documents(
        {
            "$or": [
                {"average_rating": {"$exists": False}},
                {"rating_sum": {"$exists": False}},
                {"rating_breakdown": {"$exists": False}},
            ]
        }
    )
    legacy_rating_remaining = products.count_documents({"rating": {"$exists": True}})

    assert missing_new_fields == 0, "products collection still missing rating aggregate fields"
    assert legacy_rating_remaining == 0, "legacy products.rating field still exists"


def test_products_rating_breakdown_shape_is_valid(mongo_db):
    products = mongo_db["products"]
    sample = products.find_one(
        {"rating_breakdown": {"$exists": True}},
        {"rating_breakdown": 1},
    )

    if sample is None:
        pytest.skip("No product documents found for rating_breakdown validation")

    breakdown = sample.get("rating_breakdown", {})

    assert isinstance(breakdown, dict)
    assert set(breakdown.keys()) == {"1", "2", "3", "4", "5"}
    assert all(isinstance(v, int) and v >= 0 for v in breakdown.values())


def test_audit_document_collections_have_current_base_fields(mongo_db):
    audit_collections = [
        "products",
        "categories",
        "users",
        "orders",
        "transactions",
        "inventory_ledger",
        "wishlists",
        "reviews",
        "device_tokens",
        "notifications",
    ]
    audit_fields = [
        "created_at",
        "updated_at",
        "deleted_at",
        "created_by",
        "updated_by",
        "deleted_by",
        "is_deleted",
    ]

    missing_by_collection = {}
    for collection_name in audit_collections:
        collection = mongo_db[collection_name]
        if collection.count_documents({}) == 0:
            continue

        missing_fields = {
            field: collection.count_documents({field: {"$exists": False}})
            for field in audit_fields
        }
        missing_fields = {
            field: count for field, count in missing_fields.items() if count > 0
        }
        if missing_fields:
            missing_by_collection[collection_name] = missing_fields

    assert missing_by_collection == {}


def test_counters_collection_matches_current_model_contract(mongo_db):
    counters = mongo_db["counters"]

    assert counters.count_documents({"key": {"$exists": False}}) == 0
    assert counters.count_documents({"seq": {"$exists": False}}) == 0
    assert counters.count_documents({"key": {"$type": "string", "$regex": r"^\s*$"}}) == 0
    assert counters.count_documents({"seq": {"$lt": 0}}) == 0
