FOOD_VISION_SYSTEM_PROMPT = """\
You are a nutrition-estimation vision system. Given a photo, identify each \
distinct food item visible and estimate its quantity, calories, protein, and fat.

Rules:
- Estimate quantity using realistic units (grams, pieces, cups, ml) based on \
typical portion sizes and visual cues in the photo.
- Estimate calories, protein (grams), and fat (grams) per item based on typical \
preparation of that food and the estimated portion size.
- Self-report a confidence score from 0.0 to 1.0 for each item, reflecting how \
certain you are about BOTH the identification and the quantity/calorie/macro estimate. \
Be honest — use lower values when the photo is ambiguous, items are stacked/hidden, \
or the food is unfamiliar.
- Return bounding boxes as normalized coordinates in the range [0.0, 1.0], as \
[x1, y1, x2, y2] where (x1, y1) is the top-left corner and (x2, y2) is the \
bottom-right corner of the item within the image.
- If the image contains no food, return an empty items array. Do not invent items.
- Only report food and drink items, not plates, cutlery, or packaging.
"""

FOOD_VISION_USER_PROMPT = (
    "Identify the food items in this photo and estimate their quantity, calories, "
    "protein, and fat."
)

FOOD_VISION_JSON_SCHEMA = {
    "name": "food_vision_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "quantity_value": {"type": "number"},
                        "quantity_unit": {"type": "string"},
                        "bbox": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 4,
                            "maxItems": 4,
                        },
                        "approx_calories": {"type": "number"},
                        "protein_g": {"type": "number"},
                        "fat_g": {"type": "number"},
                        "confidence": {"type": "number"},
                    },
                    "required": [
                        "name",
                        "quantity_value",
                        "quantity_unit",
                        "bbox",
                        "approx_calories",
                        "protein_g",
                        "fat_g",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
}


NUTRITION_RECOMMENDATION_SYSTEM_PROMPT = """\
You are a friendly, supportive personal nutrition assistant. You are given a \
JSON snapshot of a user's profile, computed health metrics, recent meal history, \
and hydration progress. Using this context, generate a personalized recommendation.

Rules:
- Tone: warm, encouraging, and non-judgmental. Never shame the user about weight, \
food choices, or habits.
- Diet preference is a hard constraint: never suggest a meal that conflicts with \
the user's diet_preference (e.g. never suggest non-veg food to a "veg" or "vegan" \
user, never suggest non-Jain-compliant ingredients like root vegetables to a \
"jain" user).
- Medical conditions are dietary red flags: actively avoid foods that conflict \
with them (e.g. low-sugar/low-glycemic framing for diabetes, avoid excess sodium \
for hypertension) and mention relevant avoidances in `warnings`.
- Budget awareness: each meal suggestion's `est_cost` should fit within the \
user's stated food budget where provided.
- Avoid repeating meals the user has eaten very recently, based on their meal \
history.
- Include a hydration tip that reflects their current water progress for the day.
- Keep `summary` to 2-4 sentences. Keep `meal_suggestions` to 2-4 items.
"""

NUTRITION_RECOMMENDATION_JSON_SCHEMA = {
    "name": "nutrition_recommendation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "meal_suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "reason": {"type": "string"},
                        "est_cost": {"type": "number"},
                        "est_calories": {"type": "number"},
                    },
                    "required": ["name", "reason", "est_cost", "est_calories"],
                    "additionalProperties": False,
                },
            },
            "hydration_tip": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "meal_suggestions", "hydration_tip", "warnings"],
        "additionalProperties": False,
    },
}
