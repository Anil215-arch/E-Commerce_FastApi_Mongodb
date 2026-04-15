from datetime import datetime, timezone
from pymongo import ReturnDocument
from app.models.counter_model import Counter

class SequenceService:
    @staticmethod
    async def next_invoice_number() -> str:
        year = datetime.now(timezone.utc).year
        counter_key = f"invoice_{year}"

        
        collection = Counter.get_pymongo_collection() # type: ignore

        # Atomically find the document, increment 'seq' by 1, and return the NEW document
        counter = await collection.find_one_and_update(
            {"key": counter_key},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        if not counter:
            raise RuntimeError(f"Database failed to return a sequence document for {counter_key}")
        
        seq = counter["seq"]
        
        # Format: INV-2026-000001
        return f"INV-{year}-{seq:06d}"