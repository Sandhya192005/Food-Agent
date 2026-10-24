import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { MealItems, SOURCE_LABEL, Warnings } from "../components/MealItems";
import { Card, Empty, ErrorNote, Loading, PageHeader } from "../components/ui";
import { api, notifyDataChanged } from "../lib/api";
import { useUser } from "../lib/auth";
import { formatDateTime, kcal, localDateKey, parseDate } from "../lib/format";
import { useAction, useQuery } from "../lib/hooks";
import type { MealDetail as MealDetailType, MealSummary } from "../lib/types";

const PAGE_SIZE = 20;

export function Meals() {
  const user = useUser();
  const [page, setPage] = useState(1);
  const { data, error, loading } = useQuery<MealSummary[]>(
    `/meals?page=${page}&page_size=${PAGE_SIZE}`,
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
      {loading && !data && <Loading />}
      <ErrorNote message={error?.message} />
      {data && data.length === 0 && page === 1 && (
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
                    <span>
                      <strong>{SOURCE_LABEL[meal.source] ?? meal.source}</strong>
                      <span className="muted small">
                        {" "}
                        · {formatDateTime(meal.captured_at, user.timezone)}
                      </span>
                      {meal.warnings.length > 0 && <span className="tag tag-warn">Check</span>}
                    </span>
                    <span>{kcal(meal.total_calories)} ›</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
      {data && (page > 1 || data.length === PAGE_SIZE) && (
        <div className="row gap-sm center-row">
          <button className="btn btn-ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>
            ← Newer
          </button>
          <span className="muted small">Page {page}</span>
          <button
            className="btn btn-ghost"
            disabled={data.length < PAGE_SIZE}
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
          title={SOURCE_LABEL[data.source] ?? data.source}
          action={<strong>{kcal(data.total_calories)}</strong>}
        >
          <div className="stack">
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
