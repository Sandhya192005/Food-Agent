import io

import pytest
from PIL import Image

from app.services.ai import vision_service
from app.services.meal_validation import RawFoodItem


def _jpeg_bytes(color=(200, 150, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color=color).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def mock_vision(monkeypatch):
    def _fake_analyze(image_bytes: bytes) -> list[RawFoodItem]:
        return [
            RawFoodItem("Idli", 150, "g", (0.1, 0.2, 0.3, 0.4), 195, 0.9),
            RawFoodItem("Sambar", 150, "g", (0.5, 0.2, 0.8, 0.4), 120, 0.8),
        ]

    calls = []
    original = _fake_analyze

    def _tracked(image_bytes: bytes) -> list[RawFoodItem]:
        calls.append(image_bytes)
        return original(image_bytes)

    monkeypatch.setattr(vision_service, "analyze_food_image", _tracked)
    return calls


def test_analyze_meal_persists_items_and_returns_response(client, auth_headers, mock_vision):
    response = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["is_duplicate"] is False
    assert body["total_calories"] == 315.0
    assert {item["name"] for item in body["items"]} == {"Idli", "Sambar"}
    assert len(mock_vision) == 1


def test_analyze_meal_rejects_unsupported_content_type(client, auth_headers, mock_vision):
    response = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_image_type"
    assert len(mock_vision) == 0


def test_analyze_meal_rejects_corrupt_image_bytes(client, auth_headers, mock_vision):
    response = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", b"totally not a jpeg", "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "corrupt_image"
    assert len(mock_vision) == 0


def test_duplicate_upload_within_window_skips_second_vision_call(client, auth_headers, mock_vision):
    image_bytes = _jpeg_bytes()

    first = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", image_bytes, "image/jpeg")},
    )
    second = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", image_bytes, "image/jpeg")},
    )

    assert first.json()["is_duplicate"] is False
    assert second.json()["is_duplicate"] is True
    assert second.json()["meal_id"] == first.json()["meal_id"]
    assert len(mock_vision) == 1  # second upload never called the vision service


def test_list_and_get_and_delete_meal(client, auth_headers, mock_vision):
    upload = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    meal_id = upload.json()["meal_id"]

    listing = client.get("/api/v1/meals", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["title"] == "Idli, Sambar"
    # Photo meals get their meal type from the time they were eaten.
    assert listing.json()[0]["meal_type"] in {"breakfast", "lunch", "dinner", "snack"}

    detail = client.get(f"/api/v1/meals/{meal_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert len(detail.json()["items"]) == 2

    delete = client.delete(f"/api/v1/meals/{meal_id}", headers=auth_headers)
    assert delete.status_code == 204

    follow_up = client.get(f"/api/v1/meals/{meal_id}", headers=auth_headers)
    assert follow_up.status_code == 404


def test_meal_not_found_for_other_users_meal(client, auth_headers, mock_vision):
    upload = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    meal_id = upload.json()["meal_id"]

    other_signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "other@example.com",
            "password": "supersecret123",
            "preferred_name": "Other",
            "age": 25,
            "gender": "female",
            "height_cm": 160,
            "weight_kg": 55,
            "medical_conditions": [],
            "goal": "maintain_weight",
            "diet_preference": "veg",
            "activity_level": "light",
            "timezone": "UTC",
        },
    ).json()
    other_headers = {"Authorization": f"Bearer {other_signup['tokens']['access_token']}"}

    response = client.get(f"/api/v1/meals/{meal_id}", headers=other_headers)
    assert response.status_code == 404


def test_meal_type_for_time_uses_meal_windows():
    from datetime import time

    from app.core.constants import MealType, meal_type_for_time

    assert meal_type_for_time(time(9, 30)) == MealType.BREAKFAST
    assert meal_type_for_time(time(14, 0)) == MealType.LUNCH
    assert meal_type_for_time(time(20, 0)) == MealType.DINNER
    assert meal_type_for_time(time(16, 0)) == MealType.SNACK
