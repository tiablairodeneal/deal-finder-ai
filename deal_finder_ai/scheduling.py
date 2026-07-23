from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


NEW_YORK_TZ = ZoneInfo("America/New_York")


def is_nine_am_new_york(instant: datetime) -> bool:
    local = instant.astimezone(NEW_YORK_TZ)
    return local.hour == 9 and local.minute == 0
