from beanie import Document
from pydantic import Field, model_validator 
from pymongo import ASCENDING, IndexModel

class Counter(Document):
    key: str = Field(..., min_length=1, max_length=100, description="Unique key for the sequence, e.g., 'invoice_2026'")
    seq: int = Field(default=0, description="The current sequence number")

    @model_validator(mode="after")
    def validate_counter(self):
        if not self.key.strip():
            raise ValueError("Counter key cannot be empty or whitespace")

        if self.seq < 0:
            raise ValueError("Counter sequence cannot be negative")

        return self

    class Settings:
        name = "counters"
        indexes = [
            IndexModel([("key", ASCENDING)], unique=True)
        ]