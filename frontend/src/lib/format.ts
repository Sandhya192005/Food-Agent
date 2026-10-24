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

// Matches MEAL_TYPE_TIME_RANGES in app/core/constants.py (user's local time,
// minutes since midnight). Keep the two in sync.
const MEAL_WINDOWS: { type: MealType; start: number; end: number; endLabel: string }[] = [
  { type: "breakfast", start: 9 * 60, end: 11 * 60, endLabel: "11:00 AM" },
  { type: "lunch", start: 13 * 60 + 30, end: 15 * 60, endLabel: "3:00 PM" },
  { type: "dinner", start: 19 * 60 + 30, end: 21 * 60, endLabel: "9:00 PM" },
];

export const MEAL_TIMES: Partial<Record<MealType, string>> = {
  breakfast: "9–11 AM",
  lunch: "1:30–3 PM",
  dinner: "7:30–9 PM",
};

function minutesInZone(date: Date, timeZone: string): number {
  const [h, m] = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  })
    .format(date)
    .split(":")
    .map(Number);
  return h * 60 + m;
}

/** A meal logged during a meal window stays "live" on the Today page until that
 *  window ends, then moves to history. Returns the end time label while live. */
export function liveUntil(
  capturedAt: string,
  timeZone: string,
  now: Date = new Date(),
): { mealType: MealType; endLabel: string } | null {
  const captured = parseDate(capturedAt);
  if (localDateKey(captured, timeZone) !== localDateKey(now, timeZone)) return null;
  const at = minutesInZone(captured, timeZone);
  const window = MEAL_WINDOWS.find((w) => at >= w.start && at < w.end);
  if (!window || minutesInZone(now, timeZone) >= window.end) return null;
  return { mealType: window.type, endLabel: window.endLabel };
}

/** True once today's window for `mealType` is over (false for snack). */
export function mealWindowEnded(mealType: MealType, timeZone: string, now: Date = new Date()): boolean {
  const window = MEAL_WINDOWS.find((w) => w.type === mealType);
  return !!window && minutesInZone(now, timeZone) >= window.end;
}

/** True while it's currently `mealType`'s window. Snack has no window, so always true. */
export function inMealWindow(mealType: MealType, timeZone: string, now: Date = new Date()): boolean {
  const window = MEAL_WINDOWS.find((w) => w.type === mealType);
  if (!window) return true;
  const at = minutesInZone(now, timeZone);
  return at >= window.start && at < window.end;
}

/** A sensible default "eaten at" time (HH:MM) when logging a missed meal. */
export const MEAL_DEFAULT_TIME: Record<MealType, string> = {
  breakfast: "09:30",
  lunch: "13:45",
  dinner: "20:00",
  snack: "16:30",
};

/** Current local time in the zone as "HH:MM". */
export function timeInZone(timeZone: string, now: Date = new Date()): string {
  const m = minutesInZone(now, timeZone);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/** The most recent date (YYYY-MM-DD, today included) that falls on `day`. */
export function lastDateFor(day: DayOfWeek, timeZone: string, now: Date = new Date()): string {
  const todayKey = localDateKey(now, timeZone);
  const [y, m, d] = todayKey.split("-").map(Number);
  const back = (DAYS.indexOf(todayInZone(timeZone, now)) - DAYS.indexOf(day) + 7) % 7;
  return new Date(Date.UTC(y, m - 1, d - back)).toISOString().slice(0, 10);
}

/** "2026-10-23" → "Fri 23 Oct" */
export function formatDateKey(key: string): string {
  return new Date(`${key}T00:00:00Z`).toLocaleDateString("en-IN", {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** "13:45" → "1:45 PM" */
export function formatClock(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}

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

export function todayInZone(timeZone: string, now: Date = new Date()): DayOfWeek {
  const name = new Intl.DateTimeFormat("en-US", { weekday: "long", timeZone }).format(now);
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

/** "9:30 AM" in the user's timezone. */
export function formatTime(value: string, timeZone: string): string {
  return parseDate(value)
    .toLocaleTimeString("en-IN", { timeZone, hour: "numeric", minute: "2-digit" })
    .toUpperCase();
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
