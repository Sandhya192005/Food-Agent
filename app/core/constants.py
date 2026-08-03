import enum


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class Goal(str, enum.Enum):
    LOSE_WEIGHT = "lose_weight"
    GAIN_WEIGHT = "gain_weight"
    MAINTAIN_WEIGHT = "maintain_weight"


class DietPreference(str, enum.Enum):
    VEG = "veg"
    NON_VEG = "non_veg"
    VEGAN = "vegan"
    JAIN = "jain"


class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}

WATER_ACTIVITY_BONUS_ML: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 0,
    ActivityLevel.LIGHT: 150,
    ActivityLevel.MODERATE: 350,
    ActivityLevel.ACTIVE: 550,
    ActivityLevel.VERY_ACTIVE: 750,
}

WATER_GOAL_ML_PER_KG = 35
WATER_GOAL_MIN_ML = 1500
WATER_GOAL_MAX_ML = 5000

DEFAULT_CURRENCY = "INR"

MEAL_STATUS_PENDING = "pending"
MEAL_STATUS_ANALYZED = "analyzed"
MEAL_STATUS_FAILED = "failed"

WATER_SOURCE_QUICK_YES = "quick_yes"
WATER_SOURCE_CUSTOM_AMOUNT = "custom_amount"
DEFAULT_QUICK_WATER_AMOUNT_ML = 250

SEED_MEDICAL_CONDITIONS = [
    "Diabetes",
    "PCOS",
    "Thyroid",
    "Hypertension",
    "High Cholesterol",
]
