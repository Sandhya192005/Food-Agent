import { useMemo, useState } from "react";

import { label } from "../lib/format";
import type { ActivityLevel, DietPreference, Gender, Goal, ProfileFields } from "../lib/types";

const GENDERS: Gender[] = ["female", "male", "other", "prefer_not_to_say"];
const GOALS: Goal[] = ["lose_weight", "maintain_weight", "gain_weight"];
const DIETS: DietPreference[] = ["veg", "non_veg", "vegan", "jain"];
const ACTIVITY: { value: ActivityLevel; hint: string }[] = [
  { value: "sedentary", hint: "Desk job, little exercise" },
  { value: "light", hint: "Exercise 1–3 days a week" },
  { value: "moderate", hint: "Exercise 3–5 days a week" },
  { value: "active", hint: "Exercise 6–7 days a week" },
  { value: "very_active", hint: "Hard exercise or physical job" },
];
// Matches SEED_MEDICAL_CONDITIONS in app/core/constants.py; others can be typed in.
const COMMON_CONDITIONS = ["Diabetes", "PCOS", "Thyroid", "Hypertension", "High Cholesterol"];

export function browserTimeZone(): string {
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  // Some browsers still report the old name; the backend docs use the new one.
  return zone === "Asia/Calcutta" ? "Asia/Kolkata" : zone;
}

export const EMPTY_PROFILE: ProfileFields = {
  preferred_name: "",
  age: 25,
  gender: "female",
  height_cm: 160,
  weight_kg: 60,
  medical_conditions: [],
  goal: "maintain_weight",
  diet_preference: "veg",
  activity_level: "light",
  daily_budget: null,
  monthly_budget: null,
  timezone: browserTimeZone(),
};

/** Profile fields shared by Sign up and the Profile page. Controlled by the parent. */
export function ProfileFieldset({ value, onChange }: {
  value: ProfileFields;
  onChange: (next: ProfileFields) => void;
}) {
  const [otherCondition, setOtherCondition] = useState("");
  const timeZones = useMemo(() => {
    const zones = Intl.supportedValuesOf?.("timeZone") ?? [];
    return zones.includes(value.timezone) ? zones : [value.timezone, ...zones];
  }, [value.timezone]);

  const set = <K extends keyof ProfileFields>(key: K, v: ProfileFields[K]) =>
    onChange({ ...value, [key]: v });

  const numberOrNull = (raw: string) => (raw === "" ? null : Number(raw));

  const toggleCondition = (name: string) => {
    const has = value.medical_conditions.some((c) => c.toLowerCase() === name.toLowerCase());
    set(
      "medical_conditions",
      has
        ? value.medical_conditions.filter((c) => c.toLowerCase() !== name.toLowerCase())
        : [...value.medical_conditions, name],
    );
  };

  const addOther = () => {
    const name = otherCondition.trim();
    if (name && !value.medical_conditions.some((c) => c.toLowerCase() === name.toLowerCase())) {
      set("medical_conditions", [...value.medical_conditions, name]);
    }
    setOtherCondition("");
  };

  const extraConditions = value.medical_conditions.filter(
    (c) => !COMMON_CONDITIONS.some((x) => x.toLowerCase() === c.toLowerCase()),
  );

  return (
    <>
      <fieldset>
        <legend>About you</legend>
        <div className="grid-2">
          <label className="field">
            <span>What should I call you?</span>
            <input
              required
              maxLength={100}
              value={value.preferred_name}
              onChange={(e) => set("preferred_name", e.target.value)}
            />
          </label>
          <label className="field">
            <span>Age</span>
            <input
              type="number"
              required
              min={1}
              max={120}
              value={value.age}
              onChange={(e) => set("age", Number(e.target.value))}
            />
          </label>
          <label className="field">
            <span>Gender</span>
            <select value={value.gender} onChange={(e) => set("gender", e.target.value as Gender)}>
              {GENDERS.map((g) => (
                <option key={g} value={g}>
                  {label(g)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timezone</span>
            <select value={value.timezone} onChange={(e) => set("timezone", e.target.value)}>
              {timeZones.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Height (cm)</span>
            <input
              type="number"
              required
              min={1}
              max={300}
              step="0.1"
              value={value.height_cm}
              onChange={(e) => set("height_cm", Number(e.target.value))}
            />
          </label>
          <label className="field">
            <span>Weight (kg)</span>
            <input
              type="number"
              required
              min={1}
              max={500}
              step="0.1"
              value={value.weight_kg}
              onChange={(e) => set("weight_kg", Number(e.target.value))}
            />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Goals and diet</legend>
        <div className="field">
          <span>Goal</span>
          <div className="chips">
            {GOALS.map((g) => (
              <button
                type="button"
                key={g}
                className={`chip ${value.goal === g ? "chip-on" : ""}`}
                aria-pressed={value.goal === g}
                onClick={() => set("goal", g)}
              >
                {label(g)}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <span>Diet</span>
          <div className="chips">
            {DIETS.map((d) => (
              <button
                type="button"
                key={d}
                className={`chip ${value.diet_preference === d ? "chip-on" : ""}`}
                aria-pressed={value.diet_preference === d}
                onClick={() => set("diet_preference", d)}
              >
                {label(d)}
              </button>
            ))}
          </div>
        </div>
        <label className="field">
          <span>Activity level</span>
          <select
            value={value.activity_level}
            onChange={(e) => set("activity_level", e.target.value as ActivityLevel)}
          >
            {ACTIVITY.map((a) => (
              <option key={a.value} value={a.value}>
                {label(a.value)} — {a.hint}
              </option>
            ))}
          </select>
        </label>
      </fieldset>

      <fieldset>
        <legend>Health conditions (optional)</legend>
        <div className="chips">
          {[...COMMON_CONDITIONS, ...extraConditions].map((name) => {
            const on = value.medical_conditions.some((c) => c.toLowerCase() === name.toLowerCase());
            return (
              <button
                type="button"
                key={name}
                className={`chip ${on ? "chip-on" : ""}`}
                aria-pressed={on}
                onClick={() => toggleCondition(name)}
              >
                {on ? "✓ " : ""}
                {name}
              </button>
            );
          })}
        </div>
        <div className="row gap-sm">
          <input
            placeholder="Other condition"
            value={otherCondition}
            onChange={(e) => setOtherCondition(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addOther();
              }
            }}
          />
          <button type="button" className="btn btn-ghost" onClick={addOther}>
            Add
          </button>
        </div>
      </fieldset>

      <fieldset>
        <legend>Food budget (optional, ₹)</legend>
        <div className="grid-2">
          <label className="field">
            <span>Per day</span>
            <input
              type="number"
              min={0}
              value={value.daily_budget ?? ""}
              onChange={(e) => set("daily_budget", numberOrNull(e.target.value))}
            />
          </label>
          <label className="field">
            <span>Per month</span>
            <input
              type="number"
              min={0}
              value={value.monthly_budget ?? ""}
              onChange={(e) => set("monthly_budget", numberOrNull(e.target.value))}
            />
          </label>
        </div>
      </fieldset>
    </>
  );
}
