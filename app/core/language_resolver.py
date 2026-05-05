from fastapi import Request

from app.core.i18n import get_language
from app.models.user_model import User


def resolve_user_language(current_user: User, request: Request) -> str:
    return getattr(current_user, "preferred_language", None) or get_language(request)
