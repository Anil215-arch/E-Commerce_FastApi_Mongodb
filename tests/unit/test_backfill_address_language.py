from copy import deepcopy

from bson import ObjectId

from scripts.backfill_address_language import (
    DEFAULT_ADDRESS_LANGUAGE,
    MISSING_ADDRESS_LANGUAGE_QUERY,
    backfill_address_language,
)


class FakeUsersCollection:
    def __init__(self, documents):
        self.documents = deepcopy(documents)
        self.find_query = None
        self.updates = []

    def find(self, query):
        self.find_query = query
        return deepcopy(self.documents)

    def update_one(self, filter_query, update):
        self.updates.append((filter_query, update))
        document_id = filter_query["_id"]
        for document in self.documents:
            if document["_id"] == document_id:
                document["addresses"] = deepcopy(update["$set"]["addresses"])
                return


def test_backfill_preserves_existing_address_languages():
    user_id = ObjectId()
    collection = FakeUsersCollection(
        [
            {
                "_id": user_id,
                "addresses": [
                    {"city": "Delhi", "language": "hi"},
                    {"city": "Tokyo", "language": "ja"},
                ],
            }
        ]
    )

    result = backfill_address_language(collection)

    assert result.users_updated == 0
    assert result.addresses_updated == 0
    assert collection.updates == []
    assert collection.find_query == MISSING_ADDRESS_LANGUAGE_QUERY


def test_backfill_sets_missing_address_language_to_en():
    first_user_id = ObjectId()
    second_user_id = ObjectId()
    collection = FakeUsersCollection(
        [
            {
                "_id": first_user_id,
                "addresses": [
                    {"city": "Bengaluru"},
                    {"city": "Delhi", "language": "hi"},
                    {"city": "Tokyo", "language": "ja"},
                ],
            },
            {
                "_id": second_user_id,
                "addresses": [
                    {"city": "Mumbai"},
                    "legacy-corrupt-address",
                ],
            },
            {"_id": ObjectId(), "addresses": []},
            {"_id": ObjectId()},
        ]
    )

    result = backfill_address_language(collection)

    assert result.users_updated == 2
    assert result.addresses_updated == 2
    assert collection.updates == [
        (
            {"_id": first_user_id},
            {
                "$set": {
                    "addresses": [
                        {"city": "Bengaluru", "language": DEFAULT_ADDRESS_LANGUAGE},
                        {"city": "Delhi", "language": "hi"},
                        {"city": "Tokyo", "language": "ja"},
                    ]
                }
            },
        ),
        (
            {"_id": second_user_id},
            {
                "$set": {
                    "addresses": [
                        {"city": "Mumbai", "language": DEFAULT_ADDRESS_LANGUAGE},
                        "legacy-corrupt-address",
                    ]
                }
            },
        ),
    ]
