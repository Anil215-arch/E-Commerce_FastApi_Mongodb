from fastapi import Request

from app.core.i18n import SUPPORTED_LANGUAGES, get_language
from app.models.user_model import User


def resolve_user_language(current_user: User, request: Request) -> str:
    preferred_language = getattr(current_user, "preferred_language", None)

    if preferred_language in SUPPORTED_LANGUAGES:
        return preferred_language

    return get_language(request)