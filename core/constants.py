from datetime import timedelta

CHANNEL_PREFIX = "ono"
CHANNEL_MIN = 1
CHANNEL_MAX = 99_999

COOLDOWN = timedelta(hours=24)
CANCEL_WINDOW = timedelta(minutes=5)
