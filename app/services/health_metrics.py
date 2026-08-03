from dataclasses import dataclass

from app.core.constants import ACTIVITY_MULTIPLIERS, ActivityLevel, Gender


@dataclass(frozen=True)
class HealthMetrics:
    bmi: float
    bmr: float
    tdee: float


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100
    return weight_kg / (height_m**2)


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: Gender) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender == Gender.MALE:
        return base + 5
    if gender == Gender.FEMALE:
        return base - 161
    # Mifflin-St Jeor is binary by design; average the male/female constants as a
    # pragmatic default for "other"/"prefer_not_to_say" (not clinically authoritative).
    return base - 78


def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]


def compute_all_metrics(
    *, weight_kg: float, height_cm: float, age: int, gender: Gender, activity_level: ActivityLevel
) -> HealthMetrics:
    bmi = calculate_bmi(weight_kg, height_cm)
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    tdee = calculate_tdee(bmr, activity_level)
    return HealthMetrics(bmi=round(bmi, 1), bmr=round(bmr, 1), tdee=round(tdee, 1))
