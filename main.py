from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.database import init_db
from app.api.api_v1.router import api_router
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)


app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}