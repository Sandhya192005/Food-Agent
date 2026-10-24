import { useState } from "react";
import type { FormEvent } from "react";

import { ProfileFieldset } from "../components/ProfileForm";
import { Card, ErrorNote, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { useAuth, useUser } from "../lib/auth";
import { useAction } from "../lib/hooks";
import type { ProfileFields, User } from "../lib/types";

function toFields(user: User): ProfileFields {
  const { id: _id, email: _email, currency: _currency, metrics: _metrics, ...fields } = user;
  return fields;
}

function bmiLabel(bmi: number): string {
  if (bmi < 18.5) return "Underweight";
  if (bmi < 25) return "Healthy range";
  if (bmi < 30) return "Overweight";
  return "Obese range";
}

export function Profile() {
  const user = useUser();
  const { setUser, logout } = useAuth();
  const [form, setForm] = useState<ProfileFields>(() => toFields(user));
  const [saved, setSaved] = useState(false);

  const save = useAction(async (fields: ProfileFields) => {
    // Only send what changed, so the backend only recomputes what it must.
    const original = toFields(user);
    const changes = Object.fromEntries(
      Object.entries(fields).filter(
        ([key, value]) =>
          JSON.stringify(value) !== JSON.stringify(original[key as keyof ProfileFields]),
      ),
    );
    if (Object.keys(changes).length === 0) return;
    const updated = await api<User>("/users/me", { method: "PATCH", json: changes });
    setUser(updated);
    setForm(toFields(updated));
  });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaved(false);
    if ((await save.run(form)).ok) setSaved(true);
  }

  const { bmi, bmr, tdee, daily_water_goal_ml } = user.metrics;

  return (
    <>
      <PageHeader
        title="Profile"
        subtitle={user.email}
        action={
          <button className="btn btn-ghost" onClick={() => logout()}>
            Log out
          </button>
        }
      />

      <div className="metric-grid">
        <Metric name="BMI" value={bmi?.toFixed(1)} hint={bmi ? bmiLabel(bmi) : undefined} />
        <Metric name="BMR" value={bmr ? `${Math.round(bmr)}` : undefined} hint="kcal at rest" />
        <Metric name="Daily calories" value={tdee ? `${Math.round(tdee)}` : undefined} hint="kcal with activity" />
        <Metric
          name="Water goal"
          value={daily_water_goal_ml ? `${(daily_water_goal_ml / 1000).toFixed(1)} L` : undefined}
          hint="per day"
        />
        <Metric name="Protein target" value={`${Math.round(user.weight_kg)} g`} hint="1 g per kg" />
      </div>

      <Card title="Edit details">
        <form className="stack" onSubmit={submit}>
          <ProfileFieldset value={form} onChange={(next) => { setForm(next); setSaved(false); }} />
          <ErrorNote message={save.error} />
          {saved && <p className="note note-success">Saved. Your targets have been updated.</p>}
          <div className="row gap-sm">
            <button className="btn btn-primary" disabled={save.busy}>
              {save.busy ? "Saving…" : "Save changes"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setForm(toFields(user))}>
              Reset
            </button>
          </div>
        </form>
      </Card>
    </>
  );
}

function Metric({ name, value, hint }: { name: string; value?: string; hint?: string }) {
  return (
    <div className="metric">
      <span className="muted small">{name}</span>
      <strong className="metric-value">{value ?? "–"}</strong>
      {hint && <span className="muted small">{hint}</span>}
    </div>
  );
}
