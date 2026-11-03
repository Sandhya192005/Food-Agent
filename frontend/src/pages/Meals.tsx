import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { MealItems, NutritionTotals, SOURCE_LABEL, Warnings } from "../components/MealItems";
import { MealPhoto } from "../components/MealPhoto";
import { Card, Empty, ErrorNote, Loading, PageHeader } from "../components/ui";
import { api, notifyDataChanged } from "../lib/api";
import { useUser } from "../lib/auth";
import {
  formatDateKey,
  formatDateTime,
  formatTime,
  kcal,
  label,
  liveUntil,
  localDateKey,
  MEAL_EMOJI,
  parseDate,
} from "../lib/format";
import { useAction, useNow, useQuery } from "../lib/hooks";
import type { MealDetail as MealDetailType, MealSummary } from "../lib/types";

const PAGE_SIZE = 20;

export function Meals() {
  const user = useUser();
  const [page, setPage] = useState(1);
  // "" = all days; otherwise a YYYY-MM-DD day to show.
  const [day, setDay] = useState("");
  const now = useNow();
  const todayKey = localDateKey(now, user.timezone);
  const { data: allMeals, error, loading } = useQuery<MealSummary[]>(
    day ? `/meals?date=${day}&page_size=100` : `/meals?page=${page}&page_size=${PAGE_SIZE}`,
  );
  // Meals still inside their meal window live on the Today page until it ends.
  const liveCount = (allMeals ?? []).filter((m) => liveUntil(m.captured_at, user.timezone, now)).length;
  const data = useMemo(
    () => allMeals?.filter((m) => !liveUntil(m.captured_at, user.timezone, now)) ?? null,
    [allMeals, user.timezone, now],
  );

  // Group by local day: "Today", "Yesterday", or a date.
  const groups = useMemo(() => {
    const todayKey = localDateKey(new Date(), user.timezone);
    const yesterdayKey = localDateKey(new Date(Date.now() - 86_400_000), user.timezone);
    const byDay = new Map<string, MealSummary[]>();
    for (const meal of data ?? []) {
      const key = localDateKey(parseDate(meal.captured_at), user.timezone);
      byDay.set(key, [...(byDay.get(key) ?? []), meal]);
    }
    return [...byDay.entries()].map(([key, meals]) => ({
      title:
        key === todayKey
          ? "Today"
          : key === yesterdayKey
            ? "Yesterday"
            : parseDate(meals[0].captured_at).toLocaleDateString("en-IN", {
                timeZone: user.timezone,
                weekday: "short",
                day: "numeric",
                month: "short",
              }),
      total: meals.reduce((sum, m) => sum + (m.total_calories ?? 0), 0),
      meals,
    }));
  }, [data, user.timezone]);

  return (
    <>
      <PageHeader
        title="Meal history"
        action={
          <Link to="/log" className="btn btn-primary">
            + Log meal
          </Link>
        }
      />
      <div className="row gap-sm wrap history-filter">
        <label className="row gap-sm">
          <span className="muted small">Show day</span>
          <input
            type="date"
            className="date-input"
            value={day}
            max={todayKey}
            onChange={(e) => {
              setDay(e.target.value);
              setPage(1);
            }}
          />
        </label>
        {day && (
          <button className="btn btn-ghost btn-sm" onClick={() => setDay("")}>
            Show all days
          </button>
        )}
      </div>
      {loading && !data && <Loading />}
      <ErrorNote message={error?.message} />
      {liveCount > 0 && (
        <p className="note live-note">
          <span className="live-dot" aria-hidden /> {liveCount} meal{liveCount > 1 ? "s are" : " is"}{" "}
          live on the <Link to="/">Today</Link> page and will show here when the meal time ends.
        </p>
      )}
      {day && data && data.length === 0 && liveCount === 0 && (
        <Card>
          <Empty icon="📅">
            <p>No meals logged on {formatDateKey(day)}.</p>
            <p className="muted small">
              Missed one? Log it from the <Link to="/menu">Office menu</Link> (up to 7 days back).
            </p>
          </Empty>
        </Card>
      )}
      {!day && data && data.length === 0 && page === 1 && liveCount === 0 && (
        <Card>
          <Empty icon="🍽️">
            <p>No meals logged yet.</p>
            <Link to="/log" className="link">
              Log your first meal
            </Link>
          </Empty>
        </Card>
      )}
      <div className="stack">
        {groups.map((group) => (
          <Card key={group.title} title={group.title} action={<span className="muted small">{kcal(group.total)}</span>}>
            <ul className="meal-list">
              {group.meals.map((meal) => (
                <li key={meal.id}>
                  <Link to={`/meals/${meal.id}`} className="meal-row">
                    <span aria-hidden className="meal-row-icon">
                      {MEAL_EMOJI[meal.meal_type]}
                    </span>
                    <span className="meal-row-main">
                      <span>
                        <strong>{label(meal.meal_type)}</strong>
                        {meal.title && <span> · {meal.title}</span>}
                        {meal.warnings.length > 0 && <span className="tag tag-warn">Check</span>}
                      </span>
                      <span className="muted small">
                        {SOURCE_LABEL[meal.source] ?? meal.source} · {formatTime(meal.captured_at, user.timezone)}
                      </span>
                    </span>
                    <span className="meal-row-kcal">{kcal(meal.total_calories)} ›</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
      {!day && allMeals && (page > 1 || allMeals.length === PAGE_SIZE) && (
        <div className="row gap-sm center-row">
          <button className="btn btn-ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>
            ← Newer
          </button>
          <span className="muted small">Page {page}</span>
          <button
            className="btn btn-ghost"
            disabled={allMeals.length < PAGE_SIZE}
            onClick={() => setPage(page + 1)}
          >
            Older →
          </button>
        </div>
      )}
    </>
  );
}

export function MealDetail() {
  const user = useUser();
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, error, loading } = useQuery<MealDetailType>(`/meals/${id}`);
  const [confirming, setConfirming] = useState(false);
  const remove = useAction(async () => {
    await api(`/meals/${id}`, { method: "DELETE" });
    // Leave first, or the refresh would refetch this now-deleted meal and show a 404.
    navigate("/meals", { replace: true });
    notifyDataChanged();
  });

  return (
    <>
      <PageHeader
        title="Meal details"
        subtitle={data ? formatDateTime(data.captured_at, user.timezone) : undefined}
        action={
          <Link to="/meals" className="btn btn-ghost">
            ← All meals
          </Link>
        }
      />
      {loading && !data && <Loading />}
      <ErrorNote message={error?.message} />
      {data && (
        <Card
          title={
            <>
              <span aria-hidden>{MEAL_EMOJI[data.meal_type]}</span> {label(data.meal_type)}
              {data.title ? ` · ${data.title}` : ""}
            </>
          }
          action={<strong>{kcal(data.total_calories)}</strong>}
        >
          <div className="stack">
            <MealPhoto key={data.id} meal={data} />
            <NutritionTotals items={data.items} calories={data.total_calories} />
            <p className="muted small">{SOURCE_LABEL[data.source] ?? data.source}</p>
            <MealItems items={data.items} />
            <Warnings warnings={data.warnings} />
            <div className="row gap-sm">
              {confirming ? (
                <>
                  <span>Delete this meal?</span>
                  <button className="btn btn-danger btn-sm" disabled={remove.busy} onClick={() => remove.run()}>
                    Yes, delete
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setConfirming(false)}>
                    Cancel
                  </button>
                </>
              ) : (
                <button className="btn btn-ghost btn-sm danger-text" onClick={() => setConfirming(true)}>
                  Delete meal
                </button>
              )}
            </div>
            <ErrorNote message={remove.error} />
          </div>
        </Card>
      )}
    </>
  );
}
