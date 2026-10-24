import { useState } from "react";
import { Link } from "react-router-dom";

import { Card, Empty, ErrorNote, Loading, PageHeader } from "../components/ui";
import { api, notifyDataChanged } from "../lib/api";
import { useUser } from "../lib/auth";
import {
  DAYS,
  formatClock,
  formatDateKey,
  inMealWindow,
  kcal,
  label,
  lastDateFor,
  localDateKey,
  MEAL_DEFAULT_TIME,
  MEAL_EMOJI,
  parseDate,
  timeInZone,
  todayInZone,
} from "../lib/format";
import { useAction, useNow, useQuery } from "../lib/hooks";
import type { DayOfWeek, MealSummary, WeeklyMenu } from "../lib/types";

export function Menu() {
  const user = useUser();
  const now = useNow();
  const today = todayInZone(user.timezone, now);
  const [day, setDay] = useState<DayOfWeek>(today);
  const { data, error, loading } = useQuery<WeeklyMenu[]>(`/menu/weekly/${day}`);
  const meals = useQuery<MealSummary[]>("/meals?page_size=100");
  // Each tab logs for its most recent date: today, or up to 6 days back.
  const dateKey = lastDateFor(day, user.timezone, now);

  return (
    <>
      <PageHeader
        title="Office menu"
        subtitle="The recurring weekly menu at the office. Missed logging a meal? Pick its day and log it with the time you ate."
      />

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
          const loggedMeal = meals.data?.find(
            (m) =>
              m.weekly_menu_id === menu.id &&
              localDateKey(parseDate(m.captured_at), user.timezone) === dateKey,
          );
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
                <LogControls
                  // Reset the time picker when switching days.
                  key={`${menu.id}-${dateKey}`}
                  menu={menu}
                  dateKey={dateKey}
                  isToday={day === today}
                  loggedMeal={loggedMeal}
                  checking={meals.loading && !meals.data}
                />
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}

function LogControls({
  menu,
  dateKey,
  isToday,
  loggedMeal,
  checking,
}: {
  menu: WeeklyMenu;
  dateKey: string;
  isToday: boolean;
  loggedMeal: MealSummary | undefined;
  checking: boolean;
}) {
  const user = useUser();
  const nowTime = timeInZone(user.timezone);
  const defaultTime = MEAL_DEFAULT_TIME[menu.meal_type];
  // One-click "I ate this" (saved as now) only during the meal's own time;
  // otherwise ask when it was eaten so history shows the right time.
  const quick = isToday && inMealWindow(menu.meal_type, user.timezone);
  const [picking, setPicking] = useState(!quick);
  const [time, setTime] = useState(isToday && defaultTime > nowTime ? nowTime : defaultTime);

  const log = useAction(async (eatenAt?: string) => {
    await api("/meals/confirm-from-menu", {
      method: "POST",
      json: { day_of_week: menu.day_of_week, meal_type: menu.meal_type, eaten_at: eatenAt },
    });
    notifyDataChanged();
  });

  if (loggedMeal) {
    const at = parseDate(loggedMeal.captured_at).toLocaleTimeString("en-IN", {
      timeZone: user.timezone,
      hour: "numeric",
      minute: "2-digit",
    });
    return (
      <Link to={`/meals/${loggedMeal.id}`} className="note note-success logged-note">
        ✅ Logged {isToday ? "today" : `on ${formatDateKey(dateKey)}`} at {at.toUpperCase()} ›
      </Link>
    );
  }
  if (checking) return null;

  if (!picking) {
    return (
      <div className="stack">
        <div className="row gap-sm wrap">
          <button className="btn btn-primary" disabled={log.busy} onClick={() => log.run()}>
            I ate this
          </button>
          <button className="btn btn-ghost" onClick={() => setPicking(true)}>
            Ate it earlier?
          </button>
        </div>
        <ErrorNote message={log.error} />
      </div>
    );
  }

  const future = isToday && time > nowTime;
  return (
    <form
      className="stack missed-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (time && !future) log.run(`${dateKey}T${time}:00`);
      }}
    >
      <p className="small">
        {isToday ? "When did you eat it today?" : `Missed it? Log it for ${formatDateKey(dateKey)}.`}
      </p>
      <div className="row gap-sm wrap">
        <label className="row gap-sm">
          <span className="muted small">Ate at</span>
          <input
            type="time"
            className="time-input"
            value={time}
            max={isToday ? nowTime : undefined}
            required
            onChange={(e) => setTime(e.target.value)}
          />
        </label>
        <button className="btn btn-primary" disabled={log.busy || !time || future}>
          Log at {time ? formatClock(time) : "…"}
        </button>
        {quick && (
          <button type="button" className="btn btn-ghost" onClick={() => setPicking(false)}>
            Cancel
          </button>
        )}
      </div>
      {future && <p className="muted small">That time hasn't come yet today.</p>}
      <ErrorNote message={log.error} />
    </form>
  );
}
