import { useState } from "react";

import { api, notifyDataChanged } from "../lib/api";
import { useAction, useQuery } from "../lib/hooks";
import type { WaterToday } from "../lib/types";
import { Card, ErrorNote, Loading, ProgressRing } from "./ui";

const QUICK_AMOUNTS = [250, 500];

export function WaterCard({ showCustom = false }: { showCustom?: boolean }) {
  const { data, error, loading } = useQuery<WaterToday>("/water/today");
  const [custom, setCustom] = useState("");
  const log = useAction(async (amount: number) => {
    await api("/water/log", {
      method: "POST",
      json:
        amount === 250
          ? { source: "quick_yes" }
          : { source: "custom_amount", amount_ml: amount },
    });
    notifyDataChanged();
  });

  return (
    <Card title="💧 Water today" className="water-card">
      {loading && !data && <Loading />}
      <ErrorNote message={error?.message} />
      {data && (
        <div className="water-body">
          <ProgressRing percent={data.percent}>
            <strong className="ring-value">{Math.round(data.percent)}%</strong>
            <span className="muted small">of goal</span>
          </ProgressRing>
          <div className="stack">
            <div>
              <div className="stat-big">
                {(data.consumed_ml / 1000).toFixed(2)} L
                <span className="muted"> / {(data.goal_ml / 1000).toFixed(1)} L</span>
              </div>
              <p className="muted small">
                {data.remaining_ml > 0
                  ? `${data.remaining_ml} ml to go`
                  : "Goal reached — nice work! 🎉"}
              </p>
            </div>
            <div className="row gap-sm wrap">
              {QUICK_AMOUNTS.map((ml) => (
                <button
                  key={ml}
                  className="btn btn-water"
                  disabled={log.busy}
                  onClick={() => log.run(ml)}
                >
                  + {ml} ml
                </button>
              ))}
            </div>
            {showCustom && (
              <form
                className="row gap-sm"
                onSubmit={(e) => {
                  e.preventDefault();
                  const amount = Number(custom);
                  if (amount > 0 && amount <= 5000) {
                    log.run(amount).then((r) => r.ok && setCustom(""));
                  }
                }}
              >
                <input
                  type="number"
                  min={1}
                  max={5000}
                  placeholder="Other amount (ml)"
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                />
                <button className="btn btn-ghost" disabled={log.busy || !custom}>
                  Log
                </button>
              </form>
            )}
            <ErrorNote message={log.error} />
          </div>
        </div>
      )}
    </Card>
  );
}
