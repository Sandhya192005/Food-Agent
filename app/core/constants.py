import enum
from datetime import time


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


class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class DayOfWeek(str, enum.Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


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

MEAL_SOURCE_PHOTO = "photo"
MEAL_SOURCE_MENU_TEMPLATE = "menu_template"

DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

# DayOfWeek members are declared Monday..Sunday above, matching DAY_NAMES' order.
# INDEX maps a day name to Python's datetime.weekday() convention (0=Monday..6=Sunday),
# used to find "today" in that enum; DISPLAY maps it to a capitalized name for output.
DAY_OF_WEEK_INDEX: dict[DayOfWeek, int] = {day: i for i, day in enumerate(DayOfWeek)}
DAY_OF_WEEK_BY_INDEX: dict[int, DayOfWeek] = {i: day for day, i in DAY_OF_WEEK_INDEX.items()}
DAY_OF_WEEK_DISPLAY: dict[DayOfWeek, str] = dict(zip(DayOfWeek, DAY_NAMES, strict=True))

# Local time-of-day windows (start inclusive, end exclusive) used to infer which
# meal type prompt to show when the client doesn't pass one explicitly. These match
# the office's actual serving hours. Anything outside all three windows falls back
# to SNACK.
MEAL_TYPE_TIME_RANGES: list[tuple[MealType, time, time]] = [
    (MealType.BREAKFAST, time(9, 0), time(11, 0)),
    (MealType.LUNCH, time(13, 30), time(15, 0)),
    (MealType.DINNER, time(19, 30), time(21, 0)),
]

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
