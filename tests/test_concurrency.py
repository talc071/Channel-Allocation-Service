"""Stress tests verifying no-double-allocation under concurrent load.

These tests shrink the channel pool via monkeypatch so we can probe race
behavior without allocating tens of thousands of rows.
"""

import asyncio

import pytest
from httpx import AsyncClient


async def test_one_channel_pool_ten_concurrent_requests_one_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec: 'no obvious double-allocation race in normal concurrent use'.

    With exactly one channel in the pool and 10 simultaneous allocate requests,
    exactly one must succeed and nine must fail with no_available_channels.
    """
    monkeypatch.setattr("services.allocation_service.CHANNEL_MAX", 1)

    tasks = [
        client.post("/allocations", json={"ad_id": f"ad-{i}", "platform": "fb"})
        for i in range(10)
    ]
    responses = await asyncio.gather(*tasks)

    successes = [r for r in responses if r.status_code == 201]
    failures = [r for r in responses if r.status_code != 201]

    assert len(successes) == 1
    assert len(failures) == 9
    assert successes[0].json()["channel"] == "ono1"

    for r in failures:
        assert r.status_code == 409
        assert r.json()["error_code"] == "no_available_channels"


async def test_concurrent_allocations_produce_unique_channels(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Many concurrent successful allocations must never reuse the same channel."""
    pool_size = 50
    monkeypatch.setattr("services.allocation_service.CHANNEL_MAX", pool_size)

    tasks = [
        client.post("/allocations", json={"ad_id": f"ad-{i}", "platform": "fb"})
        for i in range(pool_size)
    ]
    responses = await asyncio.gather(*tasks)

    assert all(r.status_code == 201 for r in responses)

    channels = [r.json()["channel"] for r in responses]
    assert len(set(channels)) == pool_size
    assert sorted(channels, key=lambda c: int(c[3:])) == [
        f"ono{i}" for i in range(1, pool_size + 1)
    ]


async def test_concurrent_overflow_only_pool_size_succeed(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If we ask for more allocations than the pool, only pool-size requests succeed."""
    pool_size = 5
    request_count = 20
    monkeypatch.setattr("services.allocation_service.CHANNEL_MAX", pool_size)

    tasks = [
        client.post("/allocations", json={"ad_id": f"ad-{i}", "platform": "fb"})
        for i in range(request_count)
    ]
    responses = await asyncio.gather(*tasks)

    successes = [r for r in responses if r.status_code == 201]
    failures = [r for r in responses if r.status_code != 201]

    assert len(successes) == pool_size
    assert len(failures) == request_count - pool_size

    channels = {r.json()["channel"] for r in successes}
    assert channels == {f"ono{i}" for i in range(1, pool_size + 1)}

    for r in failures:
        assert r.status_code == 409
        assert r.json()["error_code"] == "no_available_channels"
