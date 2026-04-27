from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from modules.platform import Platform

AllocationStatus = Literal["active", "freed", "canceled"]


@dataclass
class Allocation:
    """Internal record of a single allocation; not exposed directly to clients."""

    id: int
    ad_id: str
    platform: Platform
    channel: str
    allocated_at: datetime
    freed_at: datetime | None = None
    available_at: datetime | None = None
    status: AllocationStatus = "active"


class AllocationRepository:
    """In-memory store. The service layer guards mutations with an asyncio.Lock."""

    def __init__(self) -> None:
        self._rows: list[Allocation] = []
        self._next_id: int = 1

    def create(
        self,
        ad_id: str,
        platform: Platform,
        channel: str,
        allocated_at: datetime,
    ) -> Allocation:
        row = Allocation(
            id=self._next_id,
            ad_id=ad_id,
            platform=platform,
            channel=channel,
            allocated_at=allocated_at,
        )
        self._next_id += 1
        self._rows.append(row)
        return row

    def get_active_by_channel(self, channel: str) -> Allocation | None:
        for row in self._rows:
            if row.status == "active" and row.channel == channel:
                return row
        return None

    def get_active_by_ad_platform(self, ad_id: str, platform: Platform) -> Allocation | None:
        for row in self._rows:
            if row.status == "active" and row.ad_id == ad_id and row.platform == platform:
                return row
        return None

    def list_active(self) -> list[Allocation]:
        active = [row for row in self._rows if row.status == "active"]
        active.sort(key=lambda r: r.allocated_at)
        return active

    def mark_freed(self, allocation: Allocation, freed_at: datetime, available_at: datetime) -> None:
        allocation.status = "freed"
        allocation.freed_at = freed_at
        allocation.available_at = available_at

    def mark_canceled(self, allocation: Allocation, canceled_at: datetime) -> None:
        # available_at = canceled_at means the channel becomes immediately reusable.
        allocation.status = "canceled"
        allocation.freed_at = None
        allocation.available_at = canceled_at

    def channels_blocked_at(self, now: datetime) -> set[str]:
        """Channels that cannot be allocated right now: active, or freed and still in cooldown."""
        blocked: set[str] = set()
        for row in self._rows:
            if row.status == "active":
                blocked.add(row.channel)
            elif row.status == "freed" and row.available_at is not None and row.available_at > now:
                blocked.add(row.channel)
        return blocked
