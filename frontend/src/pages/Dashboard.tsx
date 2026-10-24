import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Bar, Card, Empty, ErrorNote, Loading, PageHeader } from "../components/ui";
import { WaterCard } from "../components/WaterCard";
import { api, notifyDataChanged } from "../lib/api";
import { useUser } from "../lib/auth";
import {
  formatTime,
  grams,
  kcal,
  label,
  liveUntil,
  localDateKey,
  MEAL_EMOJI,
  MEAL_TIMES,
  mealWindowEnded,
  money,
  parseDate,
  todayInZone,
} from "../lib/format";
import { useAction, useNow, useQuery } from "../lib/hooks";
import type {
  MealDetail,
  MealSummary,
  MealType,
  MenuPrompt,
  Recommendation,
  SkippedMeal,
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

/** Today's office menu. During a meal window it asks "Is your lunch going to be …?"
 *  (Yes logs it, No goes to photo upload, or "I skipped it"). Once logged, the meal
 *  stays "live" here until the meal window ends, then moves to meal history.
 *  Skipped meals are never stored as meals, so they stay out of history. */
function MenuPromptCard() {
  const user = useUser();
  const now = useNow();
  const { data, error, loading, reload } = useQuery<MenuPrompt>("/menu/today-prompt");
  const todayMenu = useQuery<WeeklyMenu[]>(`/menu/weekly/${todayInZone(user.timezone)}`);
  const meals = useQuery<MealSummary[]>("/meals?page_size=100");
  const skips = useQuery<SkippedMeal[]>("/skipped-meals");
  const navigate = useNavigate();

  // The current meal depends on the clock, so re-check every minute.
  useEffect(() => {
    const timer = window.setInterval(reload, 60_000);
    return () => window.clearInterval(timer);
  }, [reload]);

  const confirm = useAction(async (weeklyMenuId: number) => {
    await api("/meals/confirm-from-menu", {
      method: "POST",
      json: { weekly_menu_id: weeklyMenuId },
    });
    notifyDataChanged();
  });
  const skip = useAction(async (mealType: MealType) => {
    await api("/skipped-meals", { method: "POST", json: { meal_type: mealType } });
    notifyDataChanged();
  });
  const undoSkip = useAction(async (skipId: number) => {
    await api(`/skipped-meals/${skipId}`, { method: "DELETE" });
    notifyDataChanged();
  });
  const skipped = new Map((skips.data ?? []).map((s) => [s.meal_type, s]));

  // Meals still inside their meal window, keyed by meal type.
  const live = new Map<MealType, { meal: MealSummary; endLabel: string }>();
  for (const meal of meals.data ?? []) {
    const info = liveUntil(meal.captured_at, user.timezone, now);
    if (info && !live.has(info.mealType)) live.set(info.mealType, { meal, endLabel: info.endLabel });
  }
  const current = data?.has_menu ? live.get(data.meal_type) : undefined;
  // Office menu meals logged any time today, keyed by menu id.
  const todayKey = localDateKey(now, user.timezone);
  const menuLoggedToday = new Map<number, MealSummary>();
  for (const meal of meals.data ?? []) {
    if (
      meal.weekly_menu_id !== null &&
      localDateKey(parseDate(meal.captured_at), user.timezone) === todayKey &&
      !menuLoggedToday.has(meal.weekly_menu_id)
    ) {
      menuLoggedToday.set(meal.weekly_menu_id, meal);
    }
  }
  // Already logged today but outside the live window (e.g. lunch logged at 1:00 PM).
  const promptLogged =
    !current && data?.weekly_menu_id != null ? menuLoggedToday.get(data.weekly_menu_id) : undefined;
  const promptSkipped = data?.has_menu && !current && !promptLogged ? skipped.get(data.meal_type) : undefined;

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
      <ErrorNote
        message={error?.message ?? todayMenu.error?.message ?? undoSkip.error ?? undefined}
      />
      <div className="stack">
        {data?.has_menu && promptLogged && (
          <Link to={`/meals/${promptLogged.id}`} className="live-meal">
            <span className="today-menu-main">
              <strong>
                ✅ {label(data.meal_type)} logged today at{" "}
                {formatTime(promptLogged.captured_at, user.timezone)} · {kcal(promptLogged.total_calories)}
              </strong>
            </span>
            <span aria-hidden>›</span>
          </Link>
        )}
        {data?.has_menu && promptSkipped && (
          <div className="skipped-meal">
            <span>
              ⏭️ <strong>{label(data.meal_type)} skipped</strong>
              <span className="muted small"> · not added to meal history</span>
            </span>
            <button
              className="btn btn-ghost btn-sm"
              disabled={undoSkip.busy}
              onClick={() => undoSkip.run(promptSkipped.id)}
            >
              Undo
            </button>
          </div>
        )}
        {data?.has_menu &&
          data.weekly_menu_id !== null &&
          !current &&
          !promptLogged &&
          !promptSkipped &&
          meals.data &&
          skips.data && (
          <div className="stack">
            <p className="menu-question">
              <span aria-hidden>{MEAL_EMOJI[data.meal_type]}</span> {data.question}
            </p>
            <div className="row gap-sm">
              <button
                className="btn btn-primary"
                disabled={confirm.busy || meals.loading}
                onClick={() => confirm.run(data.weekly_menu_id!)}
              >
                Yes, log it
              </button>
              <button className="btn btn-ghost" onClick={() => navigate("/log")}>
                No, I'll add a photo
              </button>
              <button
                className="btn btn-ghost"
                disabled={skip.busy}
                onClick={() => skip.run(data.meal_type)}
              >
                I skipped it
              </button>
            </div>
            <ErrorNote message={confirm.error ?? skip.error} />
          </div>
        )}
        {data?.has_menu && current && (
          <Link to={`/meals/${current.meal.id}`} className="live-meal">
            <span className="live-dot" aria-hidden />
            <span className="today-menu-main">
              <strong>
                ✅ {label(data.meal_type)} logged · {kcal(current.meal.total_calories)}
              </strong>
              <span className="muted small">
                Live until {current.endLabel}, then it moves to meal history
              </span>
            </span>
            <span aria-hidden>›</span>
          </Link>
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
              const loggedMeal = menuLoggedToday.get(menu.id) ?? live.get(menu.meal_type)?.meal;
              const logged = loggedMeal !== undefined;
              const skippedMeal = logged ? undefined : skipped.get(menu.meal_type);
              const missed =
                !logged &&
                !skippedMeal &&
                !isNow &&
                meals.data &&
                skips.data &&
                mealWindowEnded(menu.meal_type, user.timezone, now);
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
                  {loggedMeal ? (
                    <span className="tag tag-now">Logged</span>
                  ) : skippedMeal ? (
                    <span className="row gap-xs">
                      <span className="tag">Skipped</span>
                      <button
                        className="link small link-btn"
                        disabled={undoSkip.busy}
                        onClick={() => undoSkip.run(skippedMeal.id)}
                      >
                        Undo
                      </button>
                    </span>
                  ) : isNow ? (
                    <span className="tag tag-now">Now</span>
                  ) : missed ? (
                    <span className="row gap-sm missed-actions">
                      <Link to="/menu" className="link small">
                        Log it
                      </Link>
                      <button
                        className="link small link-btn"
                        disabled={skip.busy}
                        onClick={() => skip.run(menu.meal_type)}
                      >
                        Skip
                      </button>
                    </span>
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
