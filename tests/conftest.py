from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from core.clock import FixedClock
from main import create_app
from repositories.allocation_repository import AllocationRepository
from services.allocation_service import AllocationService


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))


@pytest.fixture
def service(clock: FixedClock) -> AllocationService:
    return AllocationService(AllocationRepository(), clock)


@pytest_asyncio.fixture
async def client(service: AllocationService) -> AsyncIterator[AsyncClient]:
    app = create_app(service=service)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
