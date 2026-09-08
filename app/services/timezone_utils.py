from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.user import User


def user_timezone(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def local_day_bounds_utc(user: User, now: datetime | None = None) -> tuple[datetime, datetime]:
    tz = user_timezone(user)
    now_local = (now or datetime.now(UTC)).astimezone(tz)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=tz)
    end_local = datetime.combine(now_local.date(), time.max, tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)
