from pydantic import BaseModel, Field, field_validator

from core.constants import CHANNEL_MAX, CHANNEL_MIN, CHANNEL_PREFIX
from modules.platform import Platform


def _validate_channel(value: str) -> str:
    """Ensure a channel string is `ono` followed by an integer in [CHANNEL_MIN, CHANNEL_MAX]."""
    if not value.startswith(CHANNEL_PREFIX):
        raise ValueError(f"channel must start with '{CHANNEL_PREFIX}'")
    suffix = value[len(CHANNEL_PREFIX):]
    if not suffix.isdigit() or suffix != str(int(suffix)):
        raise ValueError(f"channel must be '{CHANNEL_PREFIX}<n>' with no leading zeros")
    n = int(suffix)
    if not (CHANNEL_MIN <= n <= CHANNEL_MAX):
        raise ValueError(f"channel index must be between {CHANNEL_MIN} and {CHANNEL_MAX}")
    return value


class AllocateRequest(BaseModel):
    ad_id: str = Field(min_length=1)
    platform: Platform

    @field_validator("ad_id")
    @classmethod
    def _strip_ad_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("ad_id must not be empty or whitespace")
        return trimmed


class FreeRequest(BaseModel):
    channel: str

    @field_validator("channel")
    @classmethod
    def _check_channel(cls, value: str) -> str:
        return _validate_channel(value)


class CancelRequest(BaseModel):
    channel: str

    @field_validator("channel")
    @classmethod
    def _check_channel(cls, value: str) -> str:
        return _validate_channel(value)
