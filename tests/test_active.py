from httpx import AsyncClient


async def test_list_active_empty_initially(client: AsyncClient) -> None:
    response = await client.get("/allocations")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_active_returns_only_active_rows(client: AsyncClient) -> None:
    await client.post("/allocations", json={"ad_id": "ad-1", "platform": "fb"})
    await client.post("/allocations", json={"ad_id": "ad-2", "platform": "ob"})
    await client.post("/allocations", json={"ad_id": "ad-3", "platform": "snp"})

    await client.post("/allocations/free", json={"channel": "ono1"})
    await client.post("/allocations/cancel", json={"channel": "ono2"})

    response = await client.get("/allocations")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["channel"] == "ono3"
    assert rows[0]["ad_id"] == "ad-3"
    assert rows[0]["platform"] == "snp"
