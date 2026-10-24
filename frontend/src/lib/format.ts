import type { DayOfWeek, MealType } from "./types";

export const DAYS: DayOfWeek[] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

export const MEAL_EMOJI: Record<MealType, string> = {
  breakfast: "🍳",
  lunch: "🍛",
  dinner: "🍲",
  snack: "🥜",
};

// Matches MEAL_TYPE_TIME_RANGES in app/core/constants.py (user's local time).
export const MEAL_TIMES: Partial<Record<MealType, string>> = {
  breakfast: "9–11 AM",
  lunch: "1:30–3 PM",
  dinner: "7:30–9 PM",
};

/** "non_veg" → "Non veg" */
export function label(value: string): string {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** SQLite gives back timestamps without a timezone; they are UTC. */
export function parseDate(value: string): Date {
  const hasZone = /(Z|[+-]\d\d:?\d\d)$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function localDateKey(date: Date, timeZone: string): string {
  return date.toLocaleDateString("en-CA", { timeZone }); // YYYY-MM-DD
}

export function todayInZone(timeZone: string): DayOfWeek {
  const name = new Intl.DateTimeFormat("en-US", { weekday: "long", timeZone }).format(new Date());
  return name.toLowerCase() as DayOfWeek;
}

export function formatDateTime(value: string, timeZone: string): string {
  return parseDate(value).toLocaleString("en-IN", {
    timeZone,
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function timeAgo(value: string): string {
  const minutes = Math.round((Date.now() - parseDate(value).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export function kcal(value: number | null | undefined): string {
  return value == null ? "–" : `${Math.round(value)} kcal`;
}

export function money(value: number, currency = "INR"): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

/** Parses the backend's "4.3 g" strings back into a number. */
export function grams(value: string | null): number {
  return value ? Number.parseFloat(value) || 0 : 0;
}
