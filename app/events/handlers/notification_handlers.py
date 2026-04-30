from app.events.order_events import OrderDeliveredEvent, OrderCancelledEvent
from app.models.notification_model import NotificationType
from app.services.notification_services import NotificationService

async def handle_order_delivered(event: OrderDeliveredEvent) -> None:
    await NotificationService.create_notification(
        user_id=event.user_id,
        title="Order Delivered",
        message=f"Good news! Your order #{event.order_id} has been delivered successfully.",
        notification_type=NotificationType.ORDER,
        metadata={"order_id": str(event.order_id)},
        translations={
            "hi": {
                "title": "ऑर्डर डिलीवर हुआ",
                "message": f"अच्छी खबर! आपका ऑर्डर #{event.order_id} सफलतापूर्वक डिलीवर हो गया है।",
            },
            "ja": {
                "title": "注文が配達されました",
                "message": f"注文 #{event.order_id} が正常に配達されました。",
            },
        },
    )

async def handle_order_cancelled(event: OrderCancelledEvent) -> None:
    await NotificationService.create_notification(
        user_id=event.user_id,
        title="Order Cancelled",
        message=f"Order #{event.order_id} was cancelled. Reason: {event.reason}.",
        notification_type=NotificationType.ORDER,
        metadata={"order_id": str(event.order_id), "reason": event.reason},
        translations={
            "hi": {
                "title": "ऑर्डर रद्द हुआ",
                "message": f"ऑर्डर #{event.order_id} रद्द कर दिया गया। कारण: {event.reason}।",
            },
            "ja": {
                "title": "注文がキャンセルされました",
                "message": f"注文 #{event.order_id} はキャンセルされました。理由: {event.reason}。",
            },
        },
    )
