from beanie import PydanticObjectId
from app.events.base import DomainEvent

class OrderDeliveredEvent(DomainEvent):
    order_id: PydanticObjectId
    user_id: PydanticObjectId

class OrderCancelledEvent(DomainEvent):
    order_id: PydanticObjectId
    user_id: PydanticObjectId
    reason: str