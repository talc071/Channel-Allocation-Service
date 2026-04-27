from httpx import AsyncClient


async def test_allocate_success_returns_smallest_channel(client: AsyncClient) -> None:
    response = await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})

    assert response.status_code == 201
    body = response.json()
    assert body["ad_id"] == "ad-1"
    assert body["platform"] == "fb"
    assert body["channel"] == "ono1"
    assert "allocated_at" in body


async def test_allocate_picks_next_smallest_when_one_active(client: AsyncClient) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})
    response = await client.post("/allocations", json={"ad_id": "ad-2", "platform": "fb"})

    assert response.status_code == 201
    assert response.json()["channel"] == "ono2"


async def test_allocate_invalid_platform_returns_422(client: AsyncClient) -> None:
    response = await client.post("/allocations", json={"ad_id": "ad-1", "platform": "tiktok"})

    assert response.status_code == 422


async def test_allocate_empty_ad_id_returns_422(client: AsyncClient) -> None:
    response = await client.post("/allocations", json={"ad_id": "   ", "platform": "fb"})

    assert response.status_code == 422


async def test_allocate_duplicate_active_ad_platform_returns_409(client: AsyncClient) -> None:
    first = await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})
    assert first.status_code == 201

    second = await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})

    assert second.status_code == 409
    body = second.json()
    assert body["error_code"] == "duplicate_active_allocation"
    assert body["details"]["existing"]["channel"] == "ono1"


async def test_allocate_same_ad_different_platform_is_allowed(client: AsyncClient) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})
    response = await client.post("/allocations", json={"ad_id": "ad-1", "platform": "ob"})

    assert response.status_code == 201
    assert response.json()["channel"] == "ono2"
