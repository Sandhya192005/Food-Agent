from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

# Real clock: freezegun's fake `date` class breaks pydantic's date fields here.
# The test user's timezone is Asia/Kolkata.
TODAY = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()


def _skip(client, headers, meal_type, skip_date=None):
    body = {"meal_type": meal_type}
    if skip_date is not None:
        body["skip_date"] = skip_date.isoformat()
    return client.post("/api/v1/skipped-meals", json=body, headers=headers)


def test_skip_meal_is_not_in_meal_history(client, auth_headers):
    skip = _skip(client, auth_headers, "breakfast")
    assert skip.status_code == 201
    assert skip.json()["skip_date"] == TODAY.isoformat()
    assert skip.json()["meal_type"] == "breakfast"

    listed = client.get("/api/v1/skipped-meals", headers=auth_headers)
    assert [s["meal_type"] for s in listed.json()] == ["breakfast"]
    assert client.get("/api/v1/meals", headers=auth_headers).json() == []


def test_skip_same_meal_twice_returns_same_skip(client, auth_headers):
    first = _skip(client, auth_headers, "lunch")
    second = _skip(client, auth_headers, "lunch")
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/v1/skipped-meals", headers=auth_headers).json()) == 1


def test_list_skipped_meals_for_another_day(client, auth_headers):
    yesterday = TODAY - timedelta(days=1)
    _skip(client, auth_headers, "dinner", yesterday)
    assert client.get("/api/v1/skipped-meals", headers=auth_headers).json() == []
    on_yesterday = client.get(
        f"/api/v1/skipped-meals?date={yesterday.isoformat()}", headers=auth_headers
    )
    assert [s["meal_type"] for s in on_yesterday.json()] == ["dinner"]


def test_undo_skip(client, auth_headers):
    skip_id = _skip(client, auth_headers, "dinner").json()["id"]
    assert (
        client.delete(f"/api/v1/skipped-meals/{skip_id}", headers=auth_headers).status_code == 204
    )
    assert (
        client.delete(f"/api/v1/skipped-meals/{skip_id}", headers=auth_headers).status_code == 404
    )
    assert client.get("/api/v1/skipped-meals", headers=auth_headers).json() == []


def test_skip_rejects_snack_future_and_old_days(client, auth_headers):
    snack = _skip(client, auth_headers, "snack")
    future = _skip(client, auth_headers, "lunch", TODAY + timedelta(days=1))
    old = _skip(client, auth_headers, "lunch", TODAY - timedelta(days=8))
    assert snack.json()["error"]["code"] == "cannot_skip"
    assert future.json()["error"]["code"] == "skip_date_in_future"
    assert old.json()["error"]["code"] == "skip_date_too_old"


def test_logging_a_skipped_meal_clears_the_skip(client, admin_auth_headers, auth_headers):
    today_name = TODAY.strftime("%A").lower()
    client.put(
        "/api/v1/menu/weekly",
        json={
            "day_of_week": today_name,
            "meal_type": "lunch",
            "label": "Curd rice",
            "items": [
                {
                    "name": "curd rice",
                    "quantity_value": 200,
                    "quantity_unit": "g",
                    "approx_calories": 250,
                }
            ],
        },
        headers=admin_auth_headers,
    )
    _skip(client, auth_headers, "lunch")

    logged = client.post(
        "/api/v1/meals/confirm-from-menu",
        json={"day_of_week": today_name, "meal_type": "lunch"},
        headers=auth_headers,
    )
    assert logged.status_code == 200
    assert client.get("/api/v1/skipped-meals", headers=auth_headers).json() == []


def test_skipped_meals_are_per_user(client, auth_headers, admin_auth_headers):
    skip_id = _skip(client, auth_headers, "lunch").json()["id"]
    other = client.delete(f"/api/v1/skipped-meals/{skip_id}", headers=admin_auth_headers)
    assert other.status_code == 404
    assert client.get("/api/v1/skipped-meals", headers=admin_auth_headers).json() == []
