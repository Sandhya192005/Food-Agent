from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import ValidationError
from app.models.meal import Meal
from app.services.meal_validation import (
    RawFoodItem,
    apply_sanity_checks,
    compute_image_hash,
    find_recent_duplicate,
    validate_content_type,
    validate_image_bytes,
    validate_size,
)


def test_validate_content_type_rejects_unsupported_type():
    with pytest.raises(ValidationError):
        validate_content_type("text/plain")


def test_validate_content_type_accepts_allowed_type():
    validate_content_type("image/jpeg")  # should not raise


def test_validate_size_rejects_oversized_upload():
    from app.core.config import settings

    too_big = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1
    with pytest.raises(ValidationError):
        validate_size(too_big)


def test_validate_image_bytes_rejects_corrupt_data():
    with pytest.raises(ValidationError):
        validate_image_bytes(b"not a real image")


def test_validate_image_bytes_accepts_real_image():
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="JPEG")
    validate_image_bytes(buf.getvalue())  # should not raise


def test_compute_image_hash_is_deterministic():
    assert compute_image_hash(b"abc") == compute_image_hash(b"abc")
    assert compute_image_hash(b"abc") != compute_image_hash(b"xyz")


def test_apply_sanity_checks_caps_implausible_item_calories():
    items = [RawFoodItem("Feast", 1, "plate", (0, 0, 1, 1), 5000, 0.9)]
    checked, warnings = apply_sanity_checks(items)
    from app.core.config import settings

    assert checked[0].approx_calories == settings.MAX_ITEM_CALORIES
    assert checked[0].is_calorie_capped is True
    assert any("implausible" in w for w in warnings)


def test_apply_sanity_checks_flags_low_confidence_without_dropping_item():
    items = [RawFoodItem("Mystery", 100, "g", (0, 0, 1, 1), 200, 0.1)]
    checked, warnings = apply_sanity_checks(items)

    assert len(checked) == 1
    assert checked[0].is_low_confidence is True
    assert any("low confidence" in w for w in warnings)


def test_apply_sanity_checks_scales_down_meal_total_over_bound():
    from app.core.config import settings

    items = [
        RawFoodItem("A", 1, "plate", (0, 0, 1, 1), 1000, 0.9),
        RawFoodItem("B", 1, "plate", (0, 0, 1, 1), 1000, 0.9),
        RawFoodItem("C", 1, "plate", (0, 0, 1, 1), 1000, 0.9),
        RawFoodItem("D", 1, "plate", (0, 0, 1, 1), 1000, 0.9),
        RawFoodItem("E", 1, "plate", (0, 0, 1, 1), 1000, 0.9),
    ]
    checked, warnings = apply_sanity_checks(items)
    total = sum(i.approx_calories for i in checked)
    assert total <= settings.MAX_MEAL_CALORIES + 0.01
    assert any("Total calorie estimate" in w for w in warnings)


def test_apply_sanity_checks_leaves_normal_items_untouched():
    items = [RawFoodItem("Idli", 150, "g", (0.1, 0.1, 0.2, 0.2), 195, 0.9)]
    checked, warnings = apply_sanity_checks(items)

    assert checked[0].approx_calories == 195
    assert checked[0].is_calorie_capped is False
    assert checked[0].is_low_confidence is False
    assert warnings == []


def test_find_recent_duplicate_matches_within_window(db_session, test_user):
    meal = Meal(
        user_id=test_user.id,
        image_path="x.jpg",
        image_hash="abc123",
        status="analyzed",
        captured_at=datetime.now(UTC),
    )
    db_session.add(meal)
    db_session.commit()

    found = find_recent_duplicate(db_session, test_user.id, "abc123")
    assert found is not None
    assert found.id == meal.id


def test_find_recent_duplicate_ignores_different_hash(db_session, test_user):
    meal = Meal(
        user_id=test_user.id,
        image_path="x.jpg",
        image_hash="abc123",
        status="analyzed",
        captured_at=datetime.now(UTC),
    )
    db_session.add(meal)
    db_session.commit()

    assert find_recent_duplicate(db_session, test_user.id, "different") is None


def test_find_recent_duplicate_ignores_stale_upload_outside_window(db_session, test_user):
    from app.core.config import settings

    stale_time = datetime.now(UTC) - timedelta(
        minutes=settings.DUPLICATE_UPLOAD_WINDOW_MINUTES + 5
    )
    meal = Meal(
        user_id=test_user.id,
        image_path="x.jpg",
        image_hash="abc123",
        status="analyzed",
        captured_at=stale_time,
    )
    db_session.add(meal)
    db_session.commit()
    db_session.execute(
        Meal.__table__.update().where(Meal.id == meal.id).values(created_at=stale_time)
    )
    db_session.commit()

    assert find_recent_duplicate(db_session, test_user.id, "abc123") is None
