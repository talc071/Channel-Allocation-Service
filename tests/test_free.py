from datetime import timedelta

from httpx import AsyncClient

from core.clock import FixedClock


async def test_free_success_sets_24h_available_at(client: AsyncClient, clock: FixedClock) -> None:
    from datetime import datetime

    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})

    response = await client.post("/allocations/free", json={"channel": "ono1"})

    assert response.status_code == 200
    body = response.json()
    assert body["channel"] == "ono1"
    freed_at = datetime.fromisoformat(body["freed_at"])
    available_at = datetime.fromisoformat(body["available_at"])
    assert freed_at == clock.now()
    assert available_at - freed_at == timedelta(hours=24)


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

    clock.set(clock.now() + timedelta(hours=24, seconds=1))

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
