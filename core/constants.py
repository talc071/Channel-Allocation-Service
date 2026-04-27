from datetime import timedelta
from zoneinfo import ZoneInfo

CHANNEL_PREFIX = "ono"
CHANNEL_MIN = 1
CHANNEL_MAX = 99_999

# Minimum cooldown buffer added to freed_at before snapping to NY midnight.
COOLDOWN = timedelta(hours=24)
CANCEL_WINDOW = timedelta(minutes=5)

# Cooldown is anchored to midnight in this timezone.
COOLDOWN_TZ = ZoneInfo("America/New_York")
