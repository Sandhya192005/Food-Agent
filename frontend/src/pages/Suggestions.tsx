import { useState } from "react";

import { Card, Empty, ErrorNote, Loading, PageHeader } from "../components/ui";
import { api, notifyDataChanged } from "../lib/api";
import { useUser } from "../lib/auth";
import { formatDateTime, kcal, money } from "../lib/format";
import { useAction, useQuery } from "../lib/hooks";
import type { Recommendation, RecommendationHistoryEntry } from "../lib/types";

export function Suggestions() {
  const latest = useQuery<Recommendation>("/recommendations/latest");
  const history = useQuery<RecommendationHistoryEntry[]>("/recommendations/history?page_size=10");
  const generate = useAction(async () => {
    await api("/recommendations", { method: "POST" });
    notifyDataChanged();
  });
  const noneYet = latest.error?.code === "no_recommendations";

  return (
    <>
      <PageHeader
        title="Suggestions"
        subtitle="Personal meal ideas from AI, based on your profile, budget, recent meals and water."
        action={
          <button className="btn btn-primary" disabled={generate.busy} onClick={() => generate.run()}>
            {generate.busy ? "Thinking…" : "✨ Get new suggestion"}
          </button>
        }
      />
      <ErrorNote message={generate.error} />

      {latest.loading && !latest.data && <Loading />}
      {noneYet && (
        <Card>
          <Empty icon="✨">
            <p>No suggestions yet.</p>
            <p className="muted small">Tap “Get new suggestion” — it takes a few seconds.</p>
          </Empty>
        </Card>
      )}
      {!noneYet && <ErrorNote message={latest.error?.message} />}
      {latest.data && <RecommendationView rec={latest.data} />}

      {history.data && history.data.length > 1 && (
        <Card title="Earlier suggestions">
          <div className="stack">
            {history.data.slice(1).map((entry) => (
              <HistoryEntry key={entry.id} entry={entry} />
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

function RecommendationView({ rec }: { rec: Recommendation }) {
  const user = useUser();
  return (
    <div className="stack">
      <Card>
        <p className="lead">{rec.summary}</p>
      </Card>
      <div className="suggestion-grid">
        {rec.meal_suggestions.map((s) => (
          <Card key={s.name} className="suggestion">
            <h3>{s.name}</h3>
            <div className="row gap-sm">
              <span className="tag">{kcal(s.est_calories)}</span>
              <span className="tag">{money(s.est_cost, user.currency)}</span>
            </div>
            <p className="muted">{s.reason}</p>
          </Card>
        ))}
      </div>
      <p className="note note-water">💧 {rec.hydration_tip}</p>
      {rec.warnings.length > 0 && (
        <div className="note note-warn">
          {rec.warnings.map((w) => (
            <p key={w}>⚠️ {w}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function HistoryEntry({ entry }: { entry: RecommendationHistoryEntry }) {
  const user = useUser();
  const [open, setOpen] = useState(false);
  return (
    <div className="history-entry">
      <button className="history-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="muted small">{formatDateTime(entry.created_at, user.timezone)}</span>
        <span className="history-summary">{entry.recommendation.summary}</span>
        <span aria-hidden>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <ul className="plain-list">
          {entry.recommendation.meal_suggestions.map((s) => (
            <li key={s.name}>
              <strong>{s.name}</strong>{" "}
              <span className="muted small">
                · {kcal(s.est_calories)} · {money(s.est_cost, user.currency)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
