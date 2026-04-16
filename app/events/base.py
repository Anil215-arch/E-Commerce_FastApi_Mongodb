from pydantic import BaseModel, Field
from datetime import datetime, timezone

class DomainEvent(BaseModel):
    # Using Pydantic ensures strict typing and native JSON serialization for future Message Brokers (Kafka/RabbitMQ)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))