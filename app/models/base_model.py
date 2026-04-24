from datetime import datetime, timezone
from typing import Optional
from beanie import Document, Insert, Replace, Save, SaveChanges, before_event, PydanticObjectId
from pydantic import Field

class AuditDocument(Document):
    # Timestamps (Automated by Beanie)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = None

    # Audit Trail (Explicitly set by Services)
    created_by: Optional[PydanticObjectId] = None
    updated_by: Optional[PydanticObjectId] = None
    deleted_by: Optional[PydanticObjectId] = None

    # Soft Delete Flag
    is_deleted: bool = Field(default=False)

    @before_event([Insert])
    def sync_creation_times(self) -> None:
        """Runs automatically before a new document is inserted."""
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at

    @before_event([Replace, Save, SaveChanges])
    def sync_update_times(self) -> None:
        """Runs automatically every time a document is modified."""
        self.updated_at = datetime.now(timezone.utc)

    async def soft_delete(self, current_user_id: PydanticObjectId) -> None:
        """
        Industry-standard soft delete execution. 
        Marks the document as deleted, records who did it, and saves it.
        """
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = current_user_id
        self.updated_by = current_user_id
        await self.save()