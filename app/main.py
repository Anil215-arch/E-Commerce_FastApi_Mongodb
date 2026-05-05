import os
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.i18n import t
from app.core.message_keys import Msg
from app.core.database import init_db
from app.api.api_v1.router import api_router
from app.core.config import settings
from app.core.exceptions import DomainValidationError
from app.events import register_event_handlers
from app.services.order_services import OrderService
from app.utils.responses import error_response, success_response
from app.schemas.common_schema import ApiResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.rate_limiter import ip_key_func, limiter, user_limiter

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    register_event_handlers()
    cleanup_task = asyncio.create_task(OrderService.run_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)
app.state.limiter = limiter
app.state.user_limiter = user_limiter
app.add_middleware(SlowAPIMiddleware)

os.makedirs("media/products", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(api_router, prefix="/api/v1")

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    # exc.detail contains the string explaining the limit (e.g., "5 per 1 minute")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=error_response(t(request, Msg.RATE_LIMIT_EXCEEDED), exc.detail),
    )
    
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "key" in exc.detail:
        key = exc.detail.get("key")
        safe_key = key if isinstance(key, str) else Msg.REQUEST_FAILED
        params = exc.detail.get("params", {})
        safe_params = params if isinstance(params, dict) else {}
        message = t(request, safe_key, **safe_params)
        data = exc.detail.get("data")
    elif isinstance(exc.detail, str):
        message = t(request, exc.detail)
        data = None
    else:
        message = t(request, Msg.REQUEST_FAILED)
        data = exc.detail

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(message, data),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_response(t(request, Msg.VALIDATION_FAILED), jsonable_encoder(exc.errors())),
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    try:
        errors = exc.errors(include_context=False)
    except TypeError:
        errors = exc.errors()

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_response(t(request, Msg.VALIDATION_FAILED), jsonable_encoder(errors)),
    )

    
@app.exception_handler(DomainValidationError)
async def domain_validation_exception_handler(request: Request, exc: DomainValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response(t(request, Msg.DOMAIN_VALIDATION_FAILED), exc.detail),
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print(f"CRITICAL ERROR: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(t(request, Msg.INTERNAL_SERVER_ERROR)),
    )

@app.get("/", response_model=ApiResponse[None], tags=["Root"], summary="Welcome")
@limiter.limit("5/minute", key_func=ip_key_func)
async def root(request: Request):
    return success_response(t(request, Msg.WELCOME, project_name=settings.PROJECT_NAME))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True
    )
