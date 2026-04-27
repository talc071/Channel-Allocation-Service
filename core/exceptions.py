from typing import Any


class DomainError(Exception):
    """Base class for business-rule violations. Mapped to HTTP errors in main.py."""

    status_code: int = 400
    error_code: str = "domain_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class InvalidPlatformError(DomainError):
    status_code = 400
    error_code = "invalid_platform"


class NoAvailableChannelError(DomainError):
    status_code = 409
    error_code = "no_available_channels"


class DuplicateActiveAllocationError(DomainError):
    status_code = 409
    error_code = "duplicate_active_allocation"


class ChannelNotActiveError(DomainError):
    status_code = 409
    error_code = "channel_not_active"


class CancelWindowExpiredError(DomainError):
    status_code = 409
    error_code = "cancel_window_expired"


class AllocationNotFoundError(DomainError):
    status_code = 404
    error_code = "allocation_not_found"
