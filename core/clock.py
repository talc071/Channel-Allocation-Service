from datetime import datetime, timezone


class Clock:
    """Real-time clock. Override in tests with FixedClock to make time deterministic."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock(Clock):
    """Test clock that returns a fixed instant; advance() moves time forward."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        self._now = value
