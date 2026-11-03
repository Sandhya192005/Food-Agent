// Mirrors the backend's Pydantic schemas in app/schemas/.

export type Gender = "male" | "female" | "other" | "prefer_not_to_say";
export type Goal = "lose_weight" | "gain_weight" | "maintain_weight";
export type DietPreference = "veg" | "non_veg" | "vegan" | "jain";
export type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type DayOfWeek =
  | "monday"
  | "tuesday"
  | "wednesday"
  | "thursday"
  | "friday"
  | "saturday"
  | "sunday";

export interface ProfileFields {
  preferred_name: string;
  age: number;
  gender: Gender;
  height_cm: number;
  weight_kg: number;
  medical_conditions: string[];
  goal: Goal;
  diet_preference: DietPreference;
  activity_level: ActivityLevel;
  daily_budget: number | null;
  monthly_budget: number | null;
  timezone: string;
}

export interface SignupRequest extends ProfileFields {
  email: string;
  password: string;
}

export interface User extends ProfileFields {
  id: number;
  email: string;
  currency: string;
  metrics: {
    bmi: number | null;
    bmr: number | null;
    tdee: number | null;
    daily_water_goal_ml: number | null;
  };
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface SignupResponse {
  user: User;
  tokens: Tokens;
}

export interface MealItem {
  name: string;
  bounding_box: number[] | null;
  quantity: string;
  approx_cal: number;
  protein: string | null;
  fat: string | null;
  confidence: number | null;
  is_low_confidence: boolean;
  is_calorie_capped: boolean;
}

export interface MealAnalyzeResponse {
  meal_id: number;
  is_duplicate: boolean;
  total_calories: number;
  items: MealItem[];
  warnings: string[];
  source: string;
}

export interface MealSummary {
  id: number;
  total_calories: number | null;
  status: string;
  source: string;
  weekly_menu_id: number | null;
  /** From the office menu, or from the time eaten. */
  meal_type: MealType;
  /** Office menu name, or the first food items ("Rice, Dal +2 more"). */
  title: string | null;
  captured_at: string;
  warnings: string[];
}

export interface MealDetail extends MealSummary {
  items: MealItem[];
  /** True for meals logged with a photo. */
  has_image: boolean;
  /** Short-lived S3 link to the photo; null when it's on local disk (use /meals/{id}/image). */
  image_url: string | null;
}

/** A meal the user skipped. Stored apart from meals, so not in history. */
export interface SkippedMeal {
  id: number;
  skip_date: string;
  meal_type: MealType;
}

export interface WeeklyMenuItem {
  id: number;
  name: string;
  quantity: string;
  approx_calories: number;
  protein_g: number | null;
  fat_g: number | null;
}

export interface WeeklyMenu {
  id: number;
  day_of_week: DayOfWeek;
  day_name: string;
  meal_type: MealType;
  label: string;
  total_calories: number;
  items: WeeklyMenuItem[];
}

export interface MenuPrompt {
  has_menu: boolean;
  day_name: string;
  meal_type: MealType;
  weekly_menu_id: number | null;
  label: string | null;
  question: string | null;
  quick_actions: string[];
}

export interface WaterToday {
  consumed_ml: number;
  goal_ml: number;
  percent: number;
  remaining_ml: number;
}

export interface WaterReminder {
  should_remind: boolean;
  reason: string;
  message: string | null;
  minutes_since_last: number;
  quick_actions: string[];
}

export interface Recommendation {
  summary: string;
  meal_suggestions: { name: string; reason: string; est_cost: number; est_calories: number }[];
  hydration_tip: string;
  warnings: string[];
}

export interface RecommendationHistoryEntry {
  id: number;
  created_at: string;
  recommendation: Recommendation;
}

export interface AppNotification {
  id: number;
  type: "water_check" | "meal_nudge" | string;
  message: string;
  status: string;
  created_at: string;
  quick_actions: string[];
}
