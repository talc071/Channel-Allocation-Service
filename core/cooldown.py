from datetime import datetime, time, timedelta, timezone

from core.constants import COOLDOWN, COOLDOWN_TZ


def calculate_available_at(freed_at: datetime) -> datetime:
    """Compute when a freed channel becomes available again.

    Rule: T1 = freed_at + 24h, then snap forward to the next midnight in
    America/New_York that occurs strictly after T1. Returned in UTC.
    """
    t1 = freed_at + COOLDOWN
    t1_local = t1.astimezone(COOLDOWN_TZ)
    # Take the local NY date of T1 and go to the start of the following day.
    # That midnight is always strictly after T1 (NY DST changes happen at 02:00,
    # so midnight always exists and is unambiguous).
    next_local_date = t1_local.date() + timedelta(days=1)
    next_midnight_local = datetime.combine(next_local_date, time.min, tzinfo=COOLDOWN_TZ)
    return next_midnight_local.astimezone(timezone.utc)
