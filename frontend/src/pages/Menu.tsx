import { useState } from "react";

import { Card, Empty, ErrorNote, Loading, PageHeader } from "../components/ui";
import { api, notifyDataChanged } from "../lib/api";
import { useUser } from "../lib/auth";
import { DAYS, kcal, label, liveUntil, MEAL_EMOJI, todayInZone } from "../lib/format";
import { useAction, useNow, useQuery } from "../lib/hooks";
import type { DayOfWeek, MealSummary, MealType, WeeklyMenu } from "../lib/types";

export function Menu() {
  const user = useUser();
  const today = todayInZone(user.timezone);
  const [day, setDay] = useState<DayOfWeek>(today);
  const { data, error, loading } = useQuery<WeeklyMenu[]>(`/menu/weekly/${day}`);
  const now = useNow();
  const meals = useQuery<MealSummary[]>("/meals?page_size=100");
  // Office meals logged today that are still within their meal time.
  const liveMenuIds = new Set(
    (meals.data ?? [])
      .filter((m) => m.weekly_menu_id !== null && liveUntil(m.captured_at, user.timezone, now))
      .map((m) => m.weekly_menu_id),
  );
  const [logged, setLogged] = useState<Record<string, string>>({});

  const confirm = useAction(async (mealType: MealType) => {
    const meal = await api<{ total_calories: number }>("/meals/confirm-from-menu", {
      method: "POST",
      json: { day_of_week: day, meal_type: mealType },
    });
    setLogged((l) => ({ ...l, [`${day}-${mealType}`]: `Logged — ${kcal(meal.total_calories)}` }));
    notifyDataChanged();
  });

  return (
    <>
      <PageHeader title="Office menu" subtitle="The recurring weekly menu at the office." />

      <div className="tabs" role="tablist" aria-label="Day of week">
        {DAYS.map((d) => (
          <button
            key={d}
            role="tab"
            aria-selected={d === day}
            className={`tab ${d === day ? "tab-on" : ""}`}
            onClick={() => setDay(d)}
          >
            {label(d).slice(0, 3)}
            {d === today && <span className="dot" aria-label="today" />}
          </button>
        ))}
      </div>

      {loading && !data && <Loading />}
      <ErrorNote message={error?.message} />
      {data && data.length === 0 && (
        <Card>
          <Empty icon="📅">
            <p>No office meals set for {label(day)}.</p>
            <p className="muted small">An admin can add them from the API docs (PUT /menu/weekly).</p>
          </Empty>
        </Card>
      )}

      <div className="menu-grid">
        {data?.map((menu) => {
          const key = `${day}-${menu.meal_type}`;
          return (
            <Card
              key={menu.id}
              title={
                <>
                  <span aria-hidden>{MEAL_EMOJI[menu.meal_type]}</span> {label(menu.meal_type)}
                </>
              }
              action={<span className="muted small">{kcal(menu.total_calories)}</span>}
            >
              <div className="stack">
                <h3 className="menu-label">{menu.label}</h3>
                <ul className="item-list">
                  {menu.items.map((item) => (
                    <li key={item.id} className="item">
                      <div className="item-main">
                        <strong>{item.name}</strong>
                        <span className="muted small">{item.quantity}</span>
                      </div>
                      <div className="item-nums">
                        <span>{kcal(item.approx_calories)}</span>
                        {item.protein_g != null && (
                          <span className="muted small">P {item.protein_g} g</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
                {day === today ? (
                  logged[key] || liveMenuIds.has(menu.id) ? (
                    <p className="note note-success">{logged[key] ?? "✅ Logged for today"}</p>
                  ) : (
                    <button
                      className="btn btn-primary"
                      disabled={confirm.busy}
                      onClick={() => confirm.run(menu.meal_type)}
                    >
                      I ate this
                    </button>
                  )
                ) : (
                  <p className="muted small">You can log this on {label(day)}.</p>
                )}
              </div>
            </Card>
          );
        })}
      </div>
      <ErrorNote message={confirm.error} />
    </>
  );
}
