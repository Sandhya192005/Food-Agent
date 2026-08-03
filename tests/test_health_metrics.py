import pytest

from app.core.constants import ActivityLevel, Gender
from app.services.health_metrics import (
    calculate_bmi,
    calculate_bmr,
    calculate_tdee,
    compute_all_metrics,
)


def test_calculate_bmi():
    assert calculate_bmi(weight_kg=70, height_cm=175) == pytest.approx(22.86, abs=0.01)


def test_calculate_bmr_male():
    bmr = calculate_bmr(weight_kg=70, height_cm=175, age=28, gender=Gender.MALE)
    assert bmr == pytest.approx(10 * 70 + 6.25 * 175 - 5 * 28 + 5)


def test_calculate_bmr_female():
    bmr = calculate_bmr(weight_kg=60, height_cm=165, age=30, gender=Gender.FEMALE)
    assert bmr == pytest.approx(10 * 60 + 6.25 * 165 - 5 * 30 - 161)


def test_calculate_bmr_other_is_average_of_male_and_female():
    base = 10 * 65 + 6.25 * 170 - 5 * 25
    male = base + 5
    female = base - 161
    other = calculate_bmr(weight_kg=65, height_cm=170, age=25, gender=Gender.OTHER)
    assert other == pytest.approx((male + female) / 2)


@pytest.mark.parametrize(
    "activity_level,multiplier",
    [
        (ActivityLevel.SEDENTARY, 1.2),
        (ActivityLevel.LIGHT, 1.375),
        (ActivityLevel.MODERATE, 1.55),
        (ActivityLevel.ACTIVE, 1.725),
        (ActivityLevel.VERY_ACTIVE, 1.9),
    ],
)
def test_calculate_tdee(activity_level, multiplier):
    assert calculate_tdee(1000, activity_level) == pytest.approx(1000 * multiplier)


def test_compute_all_metrics_rounds_to_one_decimal():
    metrics = compute_all_metrics(
        weight_kg=70,
        height_cm=175,
        age=28,
        gender=Gender.MALE,
        activity_level=ActivityLevel.MODERATE,
    )
    assert metrics.bmi == round(metrics.bmi, 1)
    assert metrics.bmr == round(metrics.bmr, 1)
    assert metrics.tdee == round(metrics.tdee, 1)
