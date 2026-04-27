from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from core.cooldown import calculate_available_at

NY_TZ = ZoneInfo("America/New_York")


def _ny_midnight_utc(year: int, month: int, day: int) -> datetime:
    """Return UTC instant for 00:00 in America/New_York on the given local date."""
    return datetime.combine(datetime(year, month, day), time.min, tzinfo=NY_TZ).astimezone(timezone.utc)


def _ny_local_to_utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """Return UTC instant for a wall-clock time in America/New_York."""
    return datetime(year, month, day, hour, minute, tzinfo=NY_TZ).astimezone(timezone.utc)


@pytest.mark.parametrize(
    ("freed_at", "expected"),
    [
        # Plain winter (EST, UTC-5).
        (
            datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            _ny_midnight_utc(2026, 1, 3),
        ),
        # Plain summer (EDT, UTC-4).
        (
            datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
            _ny_midnight_utc(2026, 7, 3),
        ),
    ],
)
def test_basic_cooldown_returns_next_ny_midnight(freed_at: datetime, expected: datetime) -> None:
    result = calculate_available_at(freed_at)

    assert result == expected
    assert result.astimezone(NY_TZ).time() == time(0, 0)


def test_dst_spring_forward_t1_after_transition() -> None:
    # 2026-03-07 12:00 UTC = 2026-03-07 07:00 EST (before spring forward).
    # T1 = 2026-03-08 12:00 UTC. By that instant, NY has switched to EDT.
    # T1 in NY = 2026-03-08 08:00 EDT, so next NY midnight = 2026-03-09 00:00 EDT.
    freed_at = datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)

    result = calculate_available_at(freed_at)

    assert result == _ny_midnight_utc(2026, 3, 9)
    assert result.astimezone(NY_TZ).utcoffset().total_seconds() == -4 * 3600


def test_dst_spring_forward_t1_lands_exactly_on_ny_midnight() -> None:
    # freed_at = 2026-03-08 04:00 UTC = 2026-03-07 23:00 EST.
    # T1 = 2026-03-09 04:00 UTC = 2026-03-09 00:00 EDT exactly.
    # Spec says "next midnight ... after T1" (strict), so we go to 2026-03-10 midnight.
    freed_at = datetime(2026, 3, 8, 4, 0, tzinfo=timezone.utc)

    result = calculate_available_at(freed_at)

    assert result == _ny_midnight_utc(2026, 3, 10)


def test_dst_fall_back_t1_after_transition() -> None:
    # 2026-10-31 12:00 UTC = 2026-10-31 08:00 EDT.
    # T1 = 2026-11-01 12:00 UTC. DST ended at 2026-11-01 02:00 EDT (06:00 UTC),
    # so at 12:00 UTC NY is back on EST. T1 in NY = 07:00 EST.
    # Next NY midnight = 2026-11-02 00:00 EST.
    freed_at = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)

    result = calculate_available_at(freed_at)

    assert result == _ny_midnight_utc(2026, 11, 2)
    assert result.astimezone(NY_TZ).utcoffset().total_seconds() == -5 * 3600


def test_freed_at_exactly_ny_midnight_skips_to_following_midnight() -> None:
    # freed_at is 2026-01-02 00:00 EST. T1 is also exactly midnight (next day).
    # Strict "after T1" means we land on the day after T1's date.
    freed_at = _ny_midnight_utc(2026, 1, 2)

    result = calculate_available_at(freed_at)

    assert result == _ny_midnight_utc(2026, 1, 4)


def test_minimum_cooldown_buffer_is_at_least_24_hours() -> None:
    freed_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    result = calculate_available_at(freed_at)

    assert result - freed_at >= timedelta(hours=24)


# ---------------------------------------------------------------------------
# Scenario A: Midnight cliff. Two freed_at instants only minutes apart
# can land on different NY dates and therefore on different available_at
# midnights. The two boundaries we care about are 23:59 and 00:01 NY-local.
# ---------------------------------------------------------------------------


def test_freed_at_2359_ny_lands_on_correct_midnight() -> None:
    # 2026-01-15 23:59 EST -> T1 = 2026-01-16 23:59 EST.
    # T1 NY date = 2026-01-16, so available_at = 2026-01-17 midnight NY.
    freed_at = _ny_local_to_utc(2026, 1, 15, 23, 59)

    result = calculate_available_at(freed_at)

    assert result == _ny_midnight_utc(2026, 1, 17)


def test_freed_at_0001_ny_lands_on_correct_midnight() -> None:
    # 2026-01-16 00:01 EST -> T1 = 2026-01-17 00:01 EST.
    # T1 NY date = 2026-01-17, so available_at = 2026-01-18 midnight NY.
    freed_at = _ny_local_to_utc(2026, 1, 16, 0, 1)

    result = calculate_available_at(freed_at)

    assert result == _ny_midnight_utc(2026, 1, 18)


def test_two_minute_gap_across_ny_midnight_yields_one_day_difference() -> None:
    # 23:59 vs the 00:01 two minutes later straddle NY midnight, which means
    # T1 lands on different NY dates, which means available_at differs by ~24h.
    before_midnight = _ny_local_to_utc(2026, 1, 15, 23, 59)
    after_midnight = _ny_local_to_utc(2026, 1, 16, 0, 1)

    assert after_midnight - before_midnight == timedelta(minutes=2)

    avail_before = calculate_available_at(before_midnight)
    avail_after = calculate_available_at(after_midnight)

    # Despite freed_at being only 2 minutes apart, available_at jumps a full day.
    assert avail_after - avail_before == timedelta(hours=24)
    assert avail_before == _ny_midnight_utc(2026, 1, 17)
    assert avail_after == _ny_midnight_utc(2026, 1, 18)


# ---------------------------------------------------------------------------
# Scenario B (extra): the ambiguous fall-back hour. On 2026-11-01, "01:30"
# happens twice in NY local time: once as EDT (UTC-4), once as EST (UTC-5).
# The function works with UTC instants so it must handle both correctly.
# ---------------------------------------------------------------------------


def test_dst_fall_back_first_ambiguous_0130_edt() -> None:
    # First 01:30 on 2026-11-01 is still EDT, i.e. 05:30 UTC.
    # T1 = 2026-11-02 05:30 UTC -> NY = 2026-11-02 00:30 EST.
    # Next NY midnight = 2026-11-03 00:00 EST.
    freed_at = datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc)

    result = calculate_available_at(freed_at)

    assert result == _ny_midnight_utc(2026, 11, 3)


def test_dst_fall_back_second_ambiguous_0130_est() -> None:
    # Second 01:30 on 2026-11-01 is EST, i.e. 06:30 UTC (one hour after the first).
    # T1 = 2026-11-02 06:30 UTC -> NY = 2026-11-02 01:30 EST.
    # Next NY midnight = 2026-11-03 00:00 EST (same as the first 01:30 case).
    freed_at = datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc)

    result = calculate_available_at(freed_at)

    assert result == _ny_midnight_utc(2026, 11, 3)
