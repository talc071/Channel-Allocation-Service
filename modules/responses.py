from datetime import datetime
from typing import Any

from pydantic import BaseModel

from modules.platform import Platform


class AllocationResponse(BaseModel):
    ad_id: str
    platform: Platform
    channel: str
    allocated_at: datetime


class FreeResponse(BaseModel):
    channel: str
    freed_at: datetime
    available_at: datetime


class CancelResponse(BaseModel):
    channel: str
    ad_id: str
    platform: Platform
    canceled_at: datetime


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] | None = None
