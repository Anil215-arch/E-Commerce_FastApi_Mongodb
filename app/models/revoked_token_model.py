from datetime import datetime, timezone

from beanie import Document
from pydantic import Field, model_validator
from pymongo import ASCENDING, IndexModel


class RevokedToken(Document):
    jti: str = Field(..., description="Unique JWT identifier")
    token_type: str = Field(..., pattern="^(access|refresh)$")
    user_id: str | None = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @model_validator(mode="after")
    def validate_revoked_token(self):
        if not self.jti.strip():
            raise ValueError("jti cannot be empty or whitespace")

        if self.user_id is not None and not str(self.user_id).strip():
            raise ValueError("user_id cannot be empty or whitespace")

        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")

        return self

    class Settings:
        name = "revoked_tokens"
        indexes = [
            IndexModel([("jti", ASCENDING)], unique=True),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
        ]
