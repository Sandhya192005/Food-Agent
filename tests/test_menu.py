from datetime import UTC, datetime

from freezegun import freeze_time

from app.core.security import create_access_token

# 2024-01-02 08:30 UTC = 2024-01-02 14:00 IST (Asia/Kolkata, UTC+5:30), a Tuesday
# within the 13:30-15:00 lunch window for the default test-fixture timezone.
TUESDAY_LUNCH_UTC = datetime(2024, 1, 2, 8, 30, 0, tzinfo=UTC)


def _create_tuesday_lunch_menu(client, admin_auth_headers):
    payload = {
        "day_of_week": "tuesday",
        "meal_type": "lunch",
        "label": "Sambar with Potato",
        "items": [
            {
                "name": "cooked white rice",
                "quantity_value": 180,
                "quantity_unit": "g",
                "approx_calories": 235,
                "protein_g": 4.3,
                "fat_g": 0.4,
            },
            {
                "name": "sambar",
                "quantity_value": 180,
                "quantity_unit": "ml",
                "approx_calories": 145,
                "protein_g": 7.5,
                "fat_g": 4.5,
            },
        ],
    }
    return client.put("/api/v1/menu/weekly", json=payload, headers=admin_auth_headers)


def test_non_admin_cannot_create_weekly_menu(client, auth_headers):
    response = _create_tuesday_lunch_menu(client, auth_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_required"


def test_admin_can_create_and_list_weekly_menu(client, admin_auth_headers, auth_headers):
    create_response = _create_tuesday_lunch_menu(client, admin_auth_headers)
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["day_name"] == "Tuesday"
    assert body["label"] == "Sambar with Potato"
    assert body["total_calories"] == 380
    assert len(body["items"]) == 2

    list_response = client.get("/api/v1/menu/weekly", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_get_menu_by_day_of_week(client, admin_auth_headers, auth_headers):
    _create_tuesday_lunch_menu(client, admin_auth_headers)
    breakfast = {
        "day_of_week": "tuesday",
        "meal_type": "breakfast",
        "label": "Idli",
        "items": [
            {
                "name": "idli",
                "quantity_value": 2,
                "quantity_unit": "piece",
                "approx_calories": 120,
            }
        ],
    }
    client.put("/api/v1/menu/weekly", json=breakfast, headers=admin_auth_headers)

    response = client.get("/api/v1/menu/weekly/tuesday", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert [m["meal_type"] for m in body] == ["breakfast", "lunch"]
    assert all(m["day_name"] == "Tuesday" for m in body)

    empty = client.get("/api/v1/menu/weekly/monday", headers=auth_headers)
    assert empty.status_code == 200
    assert empty.json() == []


def test_get_menu_by_invalid_day_returns_422(client, auth_headers):
    response = client.get("/api/v1/menu/weekly/funday", headers=auth_headers)
    assert response.status_code == 422


def test_admin_put_upserts_same_day_mealtype(client, admin_auth_headers):
    _create_tuesday_lunch_menu(client, admin_auth_headers)

    second_payload = {
        "day_of_week": "tuesday",
        "meal_type": "lunch",
        "label": "Curd Rice",
        "items": [
            {
                "name": "curd rice",
                "quantity_value": 200,
                "quantity_unit": "g",
                "approx_calories": 210,
            }
        ],
    }
    response = client.put("/api/v1/menu/weekly", json=second_payload, headers=admin_auth_headers)
    assert response.status_code == 200
    assert response.json()["label"] == "Curd Rice"
    assert len(response.json()["items"]) == 1


def test_today_prompt_returns_menu_for_matching_day_and_mealtype(
    client, admin_auth_headers, auth_headers, test_user
):
    _create_tuesday_lunch_menu(client, admin_auth_headers)

    # Minted inside the frozen block: a token built beforehand carries a real
    # "now" `iat`, which PyJWT rejects as issued-in-the-future once the clock is
    # frozen to a past date (2024) for this test.
    with freeze_time(TUESDAY_LUNCH_UTC):
        frozen_headers = {"Authorization": f"Bearer {create_access_token(test_user.id)}"}
        response = client.get("/api/v1/menu/today-prompt", headers=frozen_headers)

    body = response.json()
    assert body["has_menu"] is True
    assert body["day_name"] == "Tuesday"
    assert body["meal_type"] == "lunch"
    assert "Sambar with Potato" in body["question"]
    assert body["quick_actions"] == ["yes", "no"]
    assert body["weekly_menu_id"] is not None


def test_today_prompt_no_menu_for_unconfigured_slot(client, test_user):
    with freeze_time(TUESDAY_LUNCH_UTC):
        frozen_headers = {"Authorization": f"Bearer {create_access_token(test_user.id)}"}
        response = client.get("/api/v1/menu/today-prompt", headers=frozen_headers)

    body = response.json()
    assert body["has_menu"] is False
    assert body["question"] == "No scheduled meal right now"
    assert body["quick_actions"] == []


def test_confirm_meal_from_menu_creates_meal_with_correct_totals(
    client, admin_auth_headers, auth_headers
):
    create_response = _create_tuesday_lunch_menu(client, admin_auth_headers)
    weekly_menu_id = create_response.json()["id"]

    response = client.post(
        "/api/v1/meals/confirm-from-menu",
        json={"weekly_menu_id": weekly_menu_id},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "menu_template"
    assert body["total_calories"] == 380
    assert len(body["items"]) == 2
    assert body["items"][0]["protein"] == "4.3 g"

    history = client.get("/api/v1/meals", headers=auth_headers)
    assert len(history.json()) == 1
    assert history.json()[0]["source"] == "menu_template"
    assert history.json()[0]["weekly_menu_id"] == weekly_menu_id
    assert history.json()[0]["meal_type"] == "lunch"
    assert history.json()[0]["title"] == "Sambar with Potato"


def test_confirm_meal_from_menu_by_day_and_meal_type(client, admin_auth_headers, auth_headers):
    _create_tuesday_lunch_menu(client, admin_auth_headers)

    response = client.post(
        "/api/v1/meals/confirm-from-menu",
        json={"day_of_week": "tuesday", "meal_type": "lunch"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["total_calories"] == 380


def test_confirm_meal_from_menu_unset_day_slot_returns_404(client, auth_headers):
    response = client.post(
        "/api/v1/meals/confirm-from-menu",
        json={"day_of_week": "monday", "meal_type": "dinner"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "menu_not_found"


def test_confirm_meal_from_menu_requires_day_and_meal_type_or_id(client, auth_headers):
    response = client.post(
        "/api/v1/meals/confirm-from-menu",
        json={"day_of_week": "tuesday"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_confirm_meal_from_menu_applies_calorie_sanity_cap(
    client, admin_auth_headers, auth_headers
):
    payload = {
        "day_of_week": "wednesday",
        "meal_type": "dinner",
        "label": "Overloaded Thali",
        "items": [
            {
                "name": "giant biryani",
                "quantity_value": 1,
                "quantity_unit": "plate",
                "approx_calories": 5000,
            }
        ],
    }
    create_response = client.put("/api/v1/menu/weekly", json=payload, headers=admin_auth_headers)
    weekly_menu_id = create_response.json()["id"]

    response = client.post(
        "/api/v1/meals/confirm-from-menu",
        json={"weekly_menu_id": weekly_menu_id},
        headers=auth_headers,
    )
    body = response.json()
    assert body["items"][0]["is_calorie_capped"] is True
    assert body["total_calories"] <= 1200
    assert len(body["warnings"]) > 0


def test_confirm_meal_from_menu_unknown_id_returns_404(client, auth_headers):
    response = client.post(
        "/api/v1/meals/confirm-from-menu",
        json={"weekly_menu_id": 999999},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_admin_can_delete_weekly_menu(client, admin_auth_headers):
    create_response = _create_tuesday_lunch_menu(client, admin_auth_headers)
    weekly_menu_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/menu/weekly/{weekly_menu_id}", headers=admin_auth_headers
    )
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/menu/weekly", headers=admin_auth_headers)
    assert list_response.json() == []


def _confirm_tuesday_lunch_at(client, test_user, frozen_now, eaten_at):
    """Log Tuesday lunch with `eaten_at` while the clock reads `frozen_now`.
    The token is minted inside the frozen block (see the today-prompt test)."""
    with freeze_time(frozen_now):
        headers = {"Authorization": f"Bearer {create_access_token(test_user.id)}"}
        response = client.post(
            "/api/v1/meals/confirm-from-menu",
            json={"day_of_week": "tuesday", "meal_type": "lunch", "eaten_at": eaten_at},
            headers=headers,
        )
        history = client.get("/api/v1/meals", headers=headers)
    return response, history


def test_confirm_meal_from_menu_with_eaten_at_backdates_meal(client, admin_auth_headers, test_user):
    _create_tuesday_lunch_menu(client, admin_auth_headers)

    # Tuesday 17:30 IST; a time without an offset is read in the user's timezone.
    response, history = _confirm_tuesday_lunch_at(
        client, test_user, "2024-01-02 12:00:00", "2024-01-02T13:45:00"
    )
    assert response.status_code == 200
    captured = datetime.fromisoformat(history.json()[0]["captured_at"])
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)
    assert captured == datetime(2024, 1, 2, 8, 15, tzinfo=UTC)


def test_confirm_meal_from_menu_rejects_eaten_at_older_than_a_week(
    client, admin_auth_headers, test_user
):
    _create_tuesday_lunch_menu(client, admin_auth_headers)
    response, _ = _confirm_tuesday_lunch_at(
        client, test_user, "2024-01-09 12:00:00", "2024-01-02T13:45:00+05:30"
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "eaten_at_too_old"


def test_confirm_meal_from_menu_rejects_future_eaten_at(client, admin_auth_headers, test_user):
    _create_tuesday_lunch_menu(client, admin_auth_headers)
    response, _ = _confirm_tuesday_lunch_at(
        client, test_user, "2024-01-02 12:00:00", "2024-01-02T20:00:00+05:30"
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "eaten_at_in_future"


def test_confirm_meal_from_menu_rejects_eaten_at_on_other_day(
    client, admin_auth_headers, test_user
):
    _create_tuesday_lunch_menu(client, admin_auth_headers)
    # Wednesday time, Tuesday menu.
    response, _ = _confirm_tuesday_lunch_at(
        client, test_user, "2024-01-03 12:00:00", "2024-01-03T13:45:00+05:30"
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "eaten_at_day_mismatch"


def test_list_meals_filters_by_local_date(client, admin_auth_headers, test_user):
    _create_tuesday_lunch_menu(client, admin_auth_headers)
    # Two Tuesday lunches a week apart, logged on the second Tuesday.
    _confirm_tuesday_lunch_at(client, test_user, "2024-01-09 12:00:00", "2024-01-09T13:45:00")
    _confirm_tuesday_lunch_at(client, test_user, "2024-01-09 12:00:00", "2024-01-02T23:30:00")

    with freeze_time("2024-01-09 12:00:00"):
        headers = {"Authorization": f"Bearer {create_access_token(test_user.id)}"}
        on_9th = client.get("/api/v1/meals?date=2024-01-09", headers=headers)
        # 23:30 IST on the 2nd is 18:00 UTC: still the 2nd in the user's timezone.
        on_2nd = client.get("/api/v1/meals?date=2024-01-02", headers=headers)
        on_3rd = client.get("/api/v1/meals?date=2024-01-03", headers=headers)
        bad = client.get("/api/v1/meals?date=not-a-date", headers=headers)

    assert len(on_9th.json()) == 1
    assert len(on_2nd.json()) == 1
    assert on_3rd.json() == []
    assert bad.status_code == 422
