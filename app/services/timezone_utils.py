from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.user import User


def user_timezone(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")
