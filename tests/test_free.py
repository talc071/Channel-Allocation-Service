from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from httpx import AsyncClient

from core.clock import FixedClock

NY_TZ = ZoneInfo("America/New_York")


async def test_free_success_sets_available_at_to_next_ny_midnight(
    client: AsyncClient, clock: FixedClock
) -> None:
    # Default clock is 2026-01-01 12:00 UTC = 2026-01-01 07:00 EST.
    # T1 = freed_at + 24h = 2026-01-02 07:00 EST.
    # Next NY midnight after T1 = 2026-01-03 00:00 EST = 2026-01-03 05:00 UTC.
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})

    response = await client.post("/allocations/free", json={"channel": "ono1"})

    assert response.status_code == 200
    body = response.json()
    assert body["channel"] == "ono1"
    freed_at = datetime.fromisoformat(body["freed_at"])
    available_at = datetime.fromisoformat(body["available_at"])
    assert freed_at == clock.now()
    assert available_at >= freed_at + timedelta(hours=24)
    assert available_at.astimezone(NY_TZ).timetuple()[3:6] == (0, 0, 0)
    assert available_at == datetime(2026, 1, 3, 5, 0, tzinfo=timezone.utc)


async def test_reallocation_during_cooldown_skips_freed_channel(
    client: AsyncClient, clock: FixedClock
) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})
    await client.post("/allocations/free", json={"channel": "ono1"})

    clock.set(clock.now() + timedelta(hours=1))

    response = await client.post("/allocations", json={"ad_id": "ad-2", "platform": "fb"})

    assert response.status_code == 201
    assert response.json()["channel"] == "ono2"


async def test_reallocation_after_cooldown_reuses_channel(
    client: AsyncClient, clock: FixedClock
) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})
    await client.post("/allocations/free", json={"channel": "ono1"})

    # available_at is 2026-01-03 05:00 UTC; advance to 1 second past that.
    clock.set(datetime(2026, 1, 3, 5, 0, 1, tzinfo=timezone.utc))

    response = await client.post("/allocations", json={"ad_id": "ad-2", "platform": "fb"})

    assert response.status_code == 201
    assert response.json()["channel"] == "ono1"


async def test_free_non_active_channel_returns_409(client: AsyncClient) -> None:
    response = await client.post("/allocations/free", json={"channel": "ono5"})

    assert response.status_code == 409
    assert response.json()["error_code"] == "channel_not_active"


async def test_free_invalid_channel_format_returns_422(client: AsyncClient) -> None:
    response = await client.post("/allocations/free", json={"channel": "abc1"})

    assert response.status_code == 422
