import asyncio
import logging
from collections import defaultdict
from typing import Callable, Type, Dict, List

from app.events.base import DomainEvent

logger = logging.getLogger(__name__)

class EventBus:
    _handlers: Dict[Type[DomainEvent], List[Callable]] = defaultdict(list)

    @classmethod
    def subscribe(cls, event_type: Type[DomainEvent], handler: Callable) -> None:
        """Registers a handler function to a specific domain event."""
        if handler not in cls._handlers[event_type]:
            cls._handlers[event_type].append(handler)

    @classmethod
    async def publish(cls, event: DomainEvent) -> None:
        """Fires an event and executes all registered handlers concurrently."""
        handlers = cls._handlers.get(type(event), [])
        if not handlers:
            logger.debug(f"No handlers subscribed to {type(event).__name__}")
            return

        # Execute handlers concurrently to prevent slow handlers from blocking each other
        tasks = [cls._safe_execute(handler, event) for handler in handlers]
        await asyncio.gather(*tasks)

    @staticmethod
    async def _safe_execute(handler: Callable, event: DomainEvent) -> None:
        """
        Executes a handler wrapped in a try/except block.
        Crucial: Prevents side-effect failures (like network timeouts on push notifications) 
        from bubbling up and crashing the core business logic.
        """
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"Error executing {handler.__name__} for {type(event).__name__}: {str(e)}", 
                exc_info=True
            )