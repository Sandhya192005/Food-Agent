from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from app.core.constants import MEAL_SOURCE_PHOTO, MEAL_STATUS_ANALYZED, NotificationStatus
from app.core.exceptions import ValidationError
from app.models.meal import Meal, MealItem
from app.models.notification import Notification
from app.models.water import WaterLog
from app.schemas.water import WaterLogRequest
from app.services import notification_service, water_service

# 2024-01-02 06:30 UTC = 2024-01-02 12:00 IST (Asia/Kolkata), inside the 11:30-12:30
# break window used by the default test-fixture timezone.
BREAK_TIME_UTC = datetime(2024, 1, 2, 6, 30, 0, tzinfo=UTC)
OUTSIDE_BREAK_UTC = datetime(2024, 1, 2, 3, 30, 0, tzinfo=UTC)  # 09:00 IST


def _add_meal_with_protein(db_session, user, protein_g: float, when: datetime):
    meal = Meal(
        user_id=user.id,
        source=MEAL_SOURCE_PHOTO,
        status=MEAL_STATUS_ANALYZED,
        total_calories=300,
        captured_at=when,
        created_by=user.id,
        updated_by=user.id,
    )
    meal.items = [
        MealItem(
            name="chicken",
            quantity_value=150,
            quantity_unit="g",
            approx_calories=300,
            protein_g=protein_g,
            created_by=user.id,
            updated_by=user.id,
        )
    ]
    db_session.add(meal)
    db_session.commit()


def test_meal_agent_fires_inside_break_window_with_protein_gap(db_session, test_user):
    with freeze_time(BREAK_TIME_UTC):
        notification_service.run_meal_agent_tick(db_session)

    notifications = db_session.query(Notification).filter_by(user_id=test_user.id).all()
    assert len(notifications) == 1
    assert notifications[0].type.value == "meal_nudge"
    assert "70g protein" in notifications[0].message  # 70kg user, 1.0 g/kg goal, 0 eaten


def test_meal_agent_does_not_fire_outside_break_window(db_session, test_user):
    with freeze_time(OUTSIDE_BREAK_UTC):
        notification_service.run_meal_agent_tick(db_session)

    assert db_session.query(Notification).filter_by(user_id=test_user.id).count() == 0


def test_meal_agent_does_not_duplicate_within_same_day(db_session, test_user):
    with freeze_time(BREAK_TIME_UTC):
        notification_service.run_meal_agent_tick(db_session)
        notification_service.run_meal_agent_tick(db_session)

    assert db_session.query(Notification).filter_by(user_id=test_user.id).count() == 1


def test_meal_agent_skips_when_protein_goal_already_met(db_session, test_user):
    with freeze_time(BREAK_TIME_UTC):
        _add_meal_with_protein(db_session, test_user, protein_g=80, when=datetime.now(UTC))
        notification_service.run_meal_agent_tick(db_session)

    assert db_session.query(Notification).filter_by(user_id=test_user.id).count() == 0


def test_water_agent_fires_after_threshold_elapses(db_session, test_user):
    start = datetime.now(UTC)
    with freeze_time(start) as frozen:
        notification_service.run_water_agent_tick(db_session)
        assert db_session.query(Notification).count() == 0  # too soon after signup

        frozen.tick(delta=timedelta(minutes=95))
        notification_service.run_water_agent_tick(db_session)

    notifications = db_session.query(Notification).filter_by(user_id=test_user.id).all()
    assert len(notifications) == 1
    assert notifications[0].type.value == "water_check"
    assert notifications[0].status == NotificationStatus.PENDING


def test_water_agent_retries_two_minutes_after_no(db_session, test_user):
    start = datetime.now(UTC)
    with freeze_time(start) as frozen:
        frozen.tick(delta=timedelta(minutes=95))
        notification_service.run_water_agent_tick(db_session)
        first = db_session.query(Notification).filter_by(user_id=test_user.id).one()

        notification_service.respond_to_notification(db_session, test_user, first.id, "no")

        frozen.tick(delta=timedelta(minutes=1))
        notification_service.run_water_agent_tick(db_session)
        assert db_session.query(Notification).filter_by(user_id=test_user.id).count() == 1

        frozen.tick(delta=timedelta(minutes=1, seconds=1))
        notification_service.run_water_agent_tick(db_session)
        assert db_session.query(Notification).filter_by(user_id=test_user.id).count() == 2


def test_water_agent_yes_logs_water_and_resets_normal_cadence(db_session, test_user):
    start = datetime.now(UTC)
    with freeze_time(start) as frozen:
        frozen.tick(delta=timedelta(minutes=95))
        notification_service.run_water_agent_tick(db_session)
        first = db_session.query(Notification).filter_by(user_id=test_user.id).one()

        notification_service.respond_to_notification(db_session, test_user, first.id, "yes")
        assert db_session.query(WaterLog).filter_by(user_id=test_user.id).count() == 1

        frozen.tick(delta=timedelta(minutes=1))
        notification_service.run_water_agent_tick(db_session)
        assert db_session.query(Notification).filter_by(user_id=test_user.id).count() == 1


def test_water_agent_auto_resolves_when_user_logs_water_directly(db_session, test_user):
    start = datetime.now(UTC)
    with freeze_time(start) as frozen:
        frozen.tick(delta=timedelta(minutes=95))
        notification_service.run_water_agent_tick(db_session)
        first = db_session.query(Notification).filter_by(user_id=test_user.id).one()
        assert first.status == NotificationStatus.PENDING

        # Tick forward so the water log's timestamp is strictly after the
        # notification's created_at, not the same frozen instant.
        frozen.tick(delta=timedelta(seconds=30))
        water_service.log_water(
            db_session, test_user, WaterLogRequest(source="custom_amount", amount_ml=300)
        )

        frozen.tick(delta=timedelta(minutes=1))
        notification_service.run_water_agent_tick(db_session)

        db_session.refresh(first)
        assert first.status == NotificationStatus.YES
        assert db_session.query(Notification).filter_by(user_id=test_user.id).count() == 1


def test_respond_twice_to_same_notification_fails(db_session, test_user):
    start = datetime.now(UTC)
    with freeze_time(start) as frozen:
        frozen.tick(delta=timedelta(minutes=95))
        notification_service.run_water_agent_tick(db_session)
        first = db_session.query(Notification).filter_by(user_id=test_user.id).one()

        notification_service.respond_to_notification(db_session, test_user, first.id, "yes")

        with pytest.raises(ValidationError):
            notification_service.respond_to_notification(db_session, test_user, first.id, "no")


def test_notifications_api_list_and_respond(client, auth_headers, db_session, test_user):
    start = datetime.now(UTC)
    with freeze_time(start) as frozen:
        frozen.tick(delta=timedelta(minutes=95))
        notification_service.run_water_agent_tick(db_session)

    response = client.get("/api/v1/notifications/pending", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["quick_actions"] == ["yes", "no"]

    notification_id = body[0]["id"]
    respond_response = client.post(
        f"/api/v1/notifications/{notification_id}/respond",
        json={"response": "yes"},
        headers=auth_headers,
    )
    assert respond_response.status_code == 200
    assert respond_response.json()["status"] == "yes"

    follow_up = client.get("/api/v1/notifications/pending", headers=auth_headers)
    assert follow_up.json() == []
