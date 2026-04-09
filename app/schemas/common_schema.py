from typing import Generic, Optional, TypeVar, List
from pydantic import BaseModel   



T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    message: str
    status: str
    data: Optional[T] = None


class PaginationMeta(BaseModel):
    has_next_page: bool
    next_cursor: Optional[str] = None

class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    meta: PaginationMeta