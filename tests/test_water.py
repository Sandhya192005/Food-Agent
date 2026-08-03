from datetime import UTC, datetime, timedelta

from freezegun import freeze_time


def test_log_water_default_amount_is_250ml(client, auth_headers):
    response = client.post("/api/v1/water/log", json={"source": "quick_yes"}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["amount_ml"] == 250


def test_log_water_custom_amount(client, auth_headers):
    response = client.post(
        "/api/v1/water/log",
        json={"amount_ml": 500, "source": "custom_amount"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["amount_ml"] == 500


def test_water_today_aggregates_multiple_logs(client, auth_headers):
    client.post("/api/v1/water/log", json={"amount_ml": 250}, headers=auth_headers)
    client.post("/api/v1/water/log", json={"amount_ml": 300}, headers=auth_headers)

    response = client.get("/api/v1/water/today", headers=auth_headers)
    body = response.json()
    assert body["consumed_ml"] == 550
    assert body["remaining_ml"] == body["goal_ml"] - 550


def test_reminder_false_immediately_after_logging(client, auth_headers):
    client.post("/api/v1/water/log", json={"amount_ml": 250}, headers=auth_headers)
    response = client.get("/api/v1/water/reminder", headers=auth_headers)
    body = response.json()
    assert body["should_remind"] is False
    assert body["reason"] == "recently_logged"


def test_reminder_true_after_threshold_elapses(client, long_lived_auth_headers):
    # Anchor freeze_time to the real "now" (rather than a fixed past date) so the
    # already-issued auth token's `iat` never ends up after the frozen clock — PyJWT
    # rejects tokens whose `iat` is in the future relative to the verification time.
    # A long-lived token is used because these tests fast-forward well past a normal
    # 30-minute access token's expiry.
    start = datetime.now(UTC)

    with freeze_time(start):
        client.post("/api/v1/water/log", json={"amount_ml": 250}, headers=long_lived_auth_headers)

    with freeze_time(start) as frozen:
        frozen.tick(delta=timedelta(minutes=95))
        response = client.get("/api/v1/water/reminder", headers=long_lived_auth_headers)

    body = response.json()
    assert body["should_remind"] is True
    assert body["minutes_since_last"] == 95
    assert set(body["quick_actions"]) == {"yes_250ml", "choose_amount", "remind_later"}


def test_snooze_suppresses_reminder_until_expiry(client, long_lived_auth_headers):
    start = datetime.now(UTC)

    with freeze_time(start):
        client.post("/api/v1/water/log", json={"amount_ml": 250}, headers=long_lived_auth_headers)

    with freeze_time(start) as frozen:
        frozen.tick(delta=timedelta(minutes=95))
        snooze_response = client.post("/api/v1/water/snooze", headers=long_lived_auth_headers)
        assert snooze_response.status_code == 204

        reminder = client.get("/api/v1/water/reminder", headers=long_lived_auth_headers)
        assert reminder.json()["should_remind"] is False
        assert reminder.json()["reason"] == "snoozed"


def test_new_log_clears_active_snooze(client, long_lived_auth_headers):
    start = datetime.now(UTC)

    with freeze_time(start) as frozen:
        client.post("/api/v1/water/log", json={"amount_ml": 250}, headers=long_lived_auth_headers)
        frozen.tick(delta=timedelta(minutes=95))
        client.post("/api/v1/water/snooze", headers=long_lived_auth_headers)

        frozen.tick(delta=timedelta(minutes=1))
        client.post("/api/v1/water/log", json={"amount_ml": 250}, headers=long_lived_auth_headers)

        frozen.tick(delta=timedelta(minutes=1))
        reminder = client.get("/api/v1/water/reminder", headers=long_lived_auth_headers)
        assert reminder.json()["reason"] == "recently_logged"
