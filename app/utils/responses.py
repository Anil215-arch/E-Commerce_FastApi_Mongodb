from typing import Any


def success_response(message: str, data: Any = None) -> dict[str, Any]:
    return {
        "message": message,
        "status": "success",
        "data": data,
    }


def error_response(message: str, data: Any = None) -> dict[str, Any]:
    return {
        "message": message,
        "status": "error",
        "data": data,
    }
