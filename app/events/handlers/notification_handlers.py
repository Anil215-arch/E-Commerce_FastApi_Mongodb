from app.events.order_events import OrderDeliveredEvent, OrderCancelledEvent
from app.models.notification_model import NotificationType
from app.services.notification_services import NotificationService

async def handle_order_delivered(event: OrderDeliveredEvent) -> None:
    await NotificationService.create_notification(
        user_id=event.user_id,
        title="Order Delivered",
        message=f"Good news! Your order #{event.order_id} has been delivered successfully.",
        notification_type=NotificationType.ORDER,
        metadata={"order_id": str(event.order_id)}
    )

async def handle_order_cancelled(event: OrderCancelledEvent) -> None:
    await NotificationService.create_notification(
        user_id=event.user_id,
        title="Order Cancelled",
        message=f"Order #{event.order_id} was cancelled. Reason: {event.reason}.",
        notification_type=NotificationType.ORDER,
        metadata={"order_id": str(event.order_id), "reason": event.reason}
    )