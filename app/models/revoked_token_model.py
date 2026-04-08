from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class RevokedToken(Document):
    jti: str = Field(..., description="Unique JWT identifier")
    token_type: str = Field(..., pattern="^(access|refresh)$")
    user_id: str | None = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "revoked_tokens"
        indexes = [
            IndexModel([("jti", ASCENDING)], unique=True),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
        ]
