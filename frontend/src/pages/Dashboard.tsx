import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Bar, Card, Empty, ErrorNote, Loading, PageHeader } from "../components/ui";
import { WaterCard } from "../components/WaterCard";
import { api, notifyDataChanged } from "../lib/api";
import { useUser } from "../lib/auth";
import {
  grams,
  kcal,
  label,
  localDateKey,
  MEAL_EMOJI,
  MEAL_TIMES,
  money,
  parseDate,
  todayInZone,
} from "../lib/format";
import { useAction, useQuery } from "../lib/hooks";
import type {
  MealDetail,
  MealSummary,
  MenuPrompt,
  Recommendation,
  WeeklyMenu,
} from "../lib/types";

export function Dashboard() {
  const user = useUser();
  const today = new Date().toLocaleDateString("en-IN", {
    timeZone: user.timezone,
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <>
      <PageHeader title={`${greeting(user.timezone)}, ${user.preferred_name}`} subtitle={today} />
      <div className="dash-grid">
        <TodayIntakeCard />
        <WaterCard />
        <MenuPromptCard />
        <SuggestionCard />
      </div>
    </>
  );
}

function greeting(timeZone: string): string {
  const hour = Number(
    new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone }).format(
      new Date(),
    ),
  );
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

/** Calories vs TDEE and protein vs the meal agent's target (1 g per kg). */
function TodayIntakeCard() {
  const user = useUser();
  const { data: meals, error, loading } = useQuery<MealSummary[]>("/meals?page_size=100");
  const [protein, setProtein] = useState<number | null>(null);

  const todays = useMemo(() => {
    const key = localDateKey(new Date(), user.timezone);
    return (meals ?? []).filter(
      (m) => localDateKey(parseDate(m.captured_at), user.timezone) === key,
    );
  }, [meals, user.timezone]);

  // The list endpoint has no protein, so read each of today's meals (usually 1–4).
  useEffect(() => {
    if (!meals) return;
    let cancelled = false;
    Promise.all(todays.map((m) => api<MealDetail>(`/meals/${m.id}`)))
      .then((details) => {
        if (cancelled) return;
        const total = details.flatMap((d) => d.items).reduce((sum, i) => sum + grams(i.protein), 0);
        setProtein(total);
      })
      .catch(() => !cancelled && setProtein(null));
    return () => {
      cancelled = true;
    };
  }, [meals, todays]);

  const calories = todays.reduce((sum, m) => sum + (m.total_calories ?? 0), 0);
  const calorieTarget = user.metrics.tdee ?? 0;
  const proteinTarget = Math.round(user.weight_kg);

  return (
    <Card
      title="🍽️ Eaten today"
      action={
        <Link to="/log" className="btn btn-primary btn-sm">
          + Log meal
        </Link>
      }
    >
      {loading && !meals && <Loading />}
      <ErrorNote message={error?.message} />
      {meals && (
        <div className="stack">
          <div>
            <div className="row between">
              <span>Calories</span>
              <span className="muted">
                <strong className="text">{Math.round(calories)}</strong>
                {calorieTarget ? ` / ${Math.round(calorieTarget)} kcal` : " kcal"}
              </span>
            </div>
            <Bar value={calories} max={calorieTarget || calories || 1} />
          </div>
          <div>
            <div className="row between">
              <span>Protein</span>
              <span className="muted">
                <strong className="text">{protein === null ? "…" : Math.round(protein)}</strong> /{" "}
                {proteinTarget} g
              </span>
            </div>
            <Bar value={protein ?? 0} max={proteinTarget} />
          </div>
          <p className="muted small">
            {todays.length === 0
              ? "Nothing logged yet today."
              : `${todays.length} meal${todays.length > 1 ? "s" : ""} logged today.`}{" "}
            The snack reminder (11:30–12:30) only fires if protein is below target.
          </p>
        </div>
      )}
    </Card>
  );
}

/** Today's office menu. During a meal window it also asks "Is your lunch going to
 *  be …?" — Yes logs it, No goes to photo upload. */
function MenuPromptCard() {
  const user = useUser();
  const { data, error, loading, reload } = useQuery<MenuPrompt>("/menu/today-prompt");
  const todayMenu = useQuery<WeeklyMenu[]>(`/menu/weekly/${todayInZone(user.timezone)}`);
  const navigate = useNavigate();

  // The current meal depends on the clock, so re-check every minute.
  useEffect(() => {
    const timer = window.setInterval(reload, 60_000);
    return () => window.clearInterval(timer);
  }, [reload]);
  const [done, setDone] = useState<string | null>(null);
  const confirm = useAction(async (weeklyMenuId: number) => {
    const meal = await api<{ total_calories: number }>("/meals/confirm-from-menu", {
      method: "POST",
      json: { weekly_menu_id: weeklyMenuId },
    });
    setDone(`Logged — ${kcal(meal.total_calories)}.`);
    notifyDataChanged();
  });

  return (
    <Card
      title="📅 Office menu"
      action={
        <Link to="/menu" className="link small">
          Full week →
        </Link>
      }
    >
      {loading && !data && <Loading />}
      <ErrorNote message={error?.message ?? todayMenu.error?.message} />
      <div className="stack">
      {data?.has_menu && data.weekly_menu_id !== null && (
        <div className="stack">
          <p className="menu-question">
            <span aria-hidden>{MEAL_EMOJI[data.meal_type]}</span> {data.question}
          </p>
          {done ? (
            <p className="note note-success">{done}</p>
          ) : (
            <div className="row gap-sm">
              <button
                className="btn btn-primary"
                disabled={confirm.busy}
                onClick={() => confirm.run(data.weekly_menu_id!)}
              >
                Yes, log it
              </button>
              <button className="btn btn-ghost" onClick={() => navigate("/log")}>
                No, I'll add a photo
              </button>
            </div>
          )}
          <ErrorNote message={confirm.error} />
        </div>
      )}
      {todayMenu.data && todayMenu.data.length === 0 && (
        <Empty icon="📅">
          <p>No office meals today.</p>
        </Empty>
      )}
      {todayMenu.data && todayMenu.data.length > 0 && (
        <ul className="today-menu">
          {todayMenu.data.map((menu) => {
            const isNow = data?.has_menu && data.meal_type === menu.meal_type;
            return (
              <li key={menu.id} className={isNow ? "today-menu-now" : ""}>
                <span aria-hidden>{MEAL_EMOJI[menu.meal_type]}</span>
                <span className="today-menu-main">
                  <strong>{menu.label}</strong>
                  <span className="muted small">
                    {label(menu.meal_type)}
                    {MEAL_TIMES[menu.meal_type] ? ` · ${MEAL_TIMES[menu.meal_type]}` : ""}
                  </span>
                </span>
                {isNow ? (
                  <span className="tag tag-now">Now</span>
                ) : (
                  <span className="muted small">{kcal(menu.total_calories)}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      </div>
    </Card>
  );
}

function SuggestionCard() {
  const user = useUser();
  const { data, error, loading } = useQuery<Recommendation>("/recommendations/latest");
  const noneYet = error?.code === "no_recommendations";

  return (
    <Card
      title="✨ Latest suggestion"
      action={
        <Link to="/suggestions" className="link small">
          More →
        </Link>
      }
    >
      {loading && !data && <Loading />}
      {noneYet && (
        <Empty icon="✨">
          <p>No suggestions yet.</p>
          <Link to="/suggestions" className="link">
            Get your first one
          </Link>
        </Empty>
      )}
      {!noneYet && <ErrorNote message={error?.message} />}
      {data && (
        <div className="stack">
          <p>{data.summary}</p>
          {data.meal_suggestions.slice(0, 2).map((s) => (
            <div className="suggestion-mini" key={s.name}>
              <strong>{s.name}</strong>
              <span className="muted small">
                {kcal(s.est_calories)} · {money(s.est_cost, user.currency)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
