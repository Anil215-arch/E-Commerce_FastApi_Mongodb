from app.events.bus import EventBus
from app.events.order_events import OrderDeliveredEvent, OrderCancelledEvent
from app.events.handlers.notification_handlers import handle_order_delivered, handle_order_cancelled

def register_event_handlers() -> None:
    """
    Binds concrete handler functions to abstract domain events.
    Must be called exactly once during the application startup lifespan.
    """
    EventBus.subscribe(OrderDeliveredEvent, handle_order_delivered)
    EventBus.subscribe(OrderCancelledEvent, handle_order_cancelled)