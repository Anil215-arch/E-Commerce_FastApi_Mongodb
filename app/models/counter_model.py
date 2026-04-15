from beanie import Document
from pydantic import Field

class Counter(Document):
    key: str = Field(..., description="Unique key for the sequence, e.g., 'invoice_2026'")
    seq: int = Field(default=0, description="The current sequence number")

    class Settings:
        name = "counters"