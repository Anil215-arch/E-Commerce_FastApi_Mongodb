from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import decode_token


def get_user_or_ip_key(request):
    auth_header = request.headers.get("authorization")

    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
            user_id = payload.get("user_id")
            if user_id:
                return f"user:{user_id}"

            email = payload.get("sub")
            if email:
                return f"user:{str(email).lower()}"
        except Exception:
            pass

    ip = get_remote_address(request)
    return f"ip:{ip}"


ip_key_func = get_remote_address

# Single Limiter instance for the entire app.
# SlowAPI's middleware reads only `app.state.limiter`; using multiple Limiter
# instances can lead to routes not being exempted correctly from auto-checking.
limiter = Limiter(key_func=get_user_or_ip_key)

# Backward-compatible alias for existing `@user_limiter.limit(...)` usage.
user_limiter = limiter
