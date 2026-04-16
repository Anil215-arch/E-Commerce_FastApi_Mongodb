import logging
from typing import Optional

logger = logging.getLogger(__name__)

class PushProvider:
    @staticmethod
    async def send_push(token: str, title: str, body: str, data: Optional[dict] = None) -> None:
        """
        Abstraction layer for push notifications. 
        Swap the logger logic below with Firebase Cloud Messaging (FCM) or APNS in production.
        """
        logger.info(f"[PUSH SENT] Token: {token} | Title: {title} | Body: {body} | Data: {data}")