from datetime import timedelta

from httpx import AsyncClient

from core.clock import FixedClock


async def test_cancel_within_window_succeeds(client: AsyncClient, clock: FixedClock) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})

    clock.set(clock.now() + timedelta(minutes=1))

    response = await client.post("/allocations/cancel", json={"channel": "ono1"})

    assert response.status_code == 200
    body = response.json()
    assert body["channel"] == "ono1"
    assert body["ad_id"] == "ad-1"
    assert body["platform"] == "fb"


async def test_cancel_at_exactly_5_minutes_succeeds(client: AsyncClient, clock: FixedClock) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})

    clock.set(clock.now() + timedelta(minutes=5))

    response = await client.post("/allocations/cancel", json={"channel": "ono1"})

    assert response.status_code == 200


async def test_cancel_after_window_returns_409(client: AsyncClient, clock: FixedClock) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})

    clock.set(clock.now() + timedelta(minutes=5, seconds=1))

    response = await client.post("/allocations/cancel", json={"channel": "ono1"})

    assert response.status_code == 409
    assert response.json()["error_code"] == "cancel_window_expired"


async def test_canceled_channel_is_immediately_reusable(
    client: AsyncClient, clock: FixedClock
) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})
    await client.post("/allocations/cancel", json={"channel": "ono1"})

    response = await client.post("/allocations", json={"ad_id": "ad-2", "platform": "fb"})

    assert response.status_code == 201
    assert response.json()["channel"] == "ono1"


async def test_cancel_unknown_channel_returns_404(client: AsyncClient) -> None:
    response = await client.post("/allocations/cancel", json={"channel": "ono99"})

    assert response.status_code == 404
    assert response.json()["error_code"] == "allocation_not_found"
