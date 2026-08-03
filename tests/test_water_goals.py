from datetime import UTC, datetime, timedelta

from app.core.constants import ActivityLevel
from app.services.water_goals import calculate_daily_water_goal_ml, should_remind


def test_daily_water_goal_scales_with_weight_and_activity():
    sedentary = calculate_daily_water_goal_ml(60, ActivityLevel.SEDENTARY)
    active = calculate_daily_water_goal_ml(60, ActivityLevel.VERY_ACTIVE)
    assert active > sedentary


def test_daily_water_goal_is_clamped_to_sane_bounds():
    assert calculate_daily_water_goal_ml(1, ActivityLevel.SEDENTARY) >= 1500
    assert calculate_daily_water_goal_ml(500, ActivityLevel.VERY_ACTIVE) <= 5000


def test_should_remind_false_when_recently_logged():
    now = datetime.now(UTC)
    remind, reason, minutes = should_remind(
        last_log_at=now - timedelta(minutes=10),
        account_created_at=now - timedelta(days=1),
        snoozed_until=None,
        now=now,
    )
    assert remind is False
    assert reason == "recently_logged"
    assert minutes == 10


def test_should_remind_true_past_threshold():
    now = datetime.now(UTC)
    remind, reason, minutes = should_remind(
        last_log_at=now - timedelta(minutes=91),
        account_created_at=now - timedelta(days=1),
        snoozed_until=None,
        now=now,
    )
    assert remind is True
    assert reason == "threshold_exceeded"
    assert minutes == 91


def test_should_remind_false_when_snoozed_even_past_threshold():
    now = datetime.now(UTC)
    remind, reason, _ = should_remind(
        last_log_at=now - timedelta(minutes=200),
        account_created_at=now - timedelta(days=1),
        snoozed_until=now + timedelta(minutes=30),
        now=now,
    )
    assert remind is False
    assert reason == "snoozed"


def test_should_remind_uses_account_created_at_when_no_logs_yet():
    now = datetime.now(UTC)
    remind, _, minutes = should_remind(
        last_log_at=None,
        account_created_at=now - timedelta(minutes=95),
        snoozed_until=None,
        now=now,
    )
    assert remind is True
    assert minutes == 95
