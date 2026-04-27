import asyncio

from core.clock import Clock
from core.constants import CANCEL_WINDOW, CHANNEL_MAX, CHANNEL_MIN, CHANNEL_PREFIX, COOLDOWN
from core.exceptions import (
    AllocationNotFoundError,
    CancelWindowExpiredError,
    ChannelNotActiveError,
    DuplicateActiveAllocationError,
    NoAvailableChannelError,
)
from modules.requests import AllocateRequest, CancelRequest, FreeRequest
from modules.responses import AllocationResponse, CancelResponse, FreeResponse
from repositories.allocation_repository import Allocation, AllocationRepository


def _to_response(row: Allocation) -> AllocationResponse:
    return AllocationResponse(
        ad_id=row.ad_id,
        platform=row.platform,
        channel=row.channel,
        allocated_at=row.allocated_at,
    )


class AllocationService:
    """Owns business rules. All write paths run under a single asyncio.Lock."""

    def __init__(self, repository: AllocationRepository, clock: Clock) -> None:
        self._repo = repository
        self._clock = clock
        self._lock = asyncio.Lock()

    async def allocate(self, req: AllocateRequest) -> AllocationResponse:
        async with self._lock:
            existing = self._repo.get_active_by_ad_platform(req.ad_id, req.platform)
            if existing is not None:
                raise DuplicateActiveAllocationError(
                    "An active allocation for this (ad_id, platform) already exists.",
                    details={"existing": _to_response(existing).model_dump(mode="json")},
                )

            now = self._clock.now()
            channel = self._pick_available_channel(now)
            row = self._repo.create(req.ad_id, req.platform, channel, now)
            return _to_response(row)

    async def free(self, req: FreeRequest) -> FreeResponse:
        async with self._lock:
            row = self._repo.get_active_by_channel(req.channel)
            if row is None:
                raise ChannelNotActiveError(
                    f"Channel {req.channel} has no active allocation.",
                    details={"channel": req.channel},
                )

            freed_at = self._clock.now()
            available_at = freed_at + COOLDOWN
            self._repo.mark_freed(row, freed_at, available_at)
            return FreeResponse(channel=row.channel, freed_at=freed_at, available_at=available_at)

    async def cancel(self, req: CancelRequest) -> CancelResponse:
        async with self._lock:
            row = self._repo.get_active_by_channel(req.channel)
            if row is None:
                raise AllocationNotFoundError(
                    f"No active allocation found for channel {req.channel}.",
                    details={"channel": req.channel},
                )

            now = self._clock.now()
            if now - row.allocated_at > CANCEL_WINDOW:
                raise CancelWindowExpiredError(
                    "Cancel window of 5 minutes has expired.",
                    details={
                        "channel": row.channel,
                        "allocated_at": row.allocated_at.isoformat(),
                        "now": now.isoformat(),
                    },
                )

            self._repo.mark_canceled(row, now)
            return CancelResponse(
                channel=row.channel,
                ad_id=row.ad_id,
                platform=row.platform,
                canceled_at=now,
            )

    def list_active(self) -> list[AllocationResponse]:
        return [_to_response(row) for row in self._repo.list_active()]

    def _pick_available_channel(self, now) -> str:
        # Smallest available numeric ono. Deterministic and easy to reason about.
        blocked = self._repo.channels_blocked_at(now)
        for i in range(CHANNEL_MIN, CHANNEL_MAX + 1):
            candidate = f"{CHANNEL_PREFIX}{i}"
            if candidate not in blocked:
                return candidate
        raise NoAvailableChannelError("No channels are currently available.")
