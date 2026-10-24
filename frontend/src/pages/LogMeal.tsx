import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { MealItems, Warnings } from "../components/MealItems";
import { Card, ErrorNote, PageHeader } from "../components/ui";
import { api, notifyDataChanged } from "../lib/api";
import { kcal } from "../lib/format";
import { useAction } from "../lib/hooks";
import type { MealAnalyzeResponse } from "../lib/types";

export function LogMeal() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<MealAnalyzeResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const analyze = useAction(async (photo: File) => {
    const form = new FormData();
    form.append("file", photo);
    const res = await api<MealAnalyzeResponse>("/meals/analyze", { method: "POST", form });
    setResult(res);
    notifyDataChanged();
  });

  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function pick(next: File | undefined) {
    if (!next) return;
    setFile(next);
    setResult(null);
    analyze.setError(null);
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setResult(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <>
      <PageHeader
        title="Log a meal"
        subtitle="Snap your plate — the AI finds each food and estimates calories."
      />
      <div className="two-col">
        <Card>
          <label
            className={`dropzone ${preview ? "has-preview" : ""}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              pick(e.dataTransfer.files[0]);
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="visually-hidden"
              onChange={(e) => pick(e.target.files?.[0])}
            />
            {preview ? (
              <img src={preview} alt="Your meal" />
            ) : (
              <span className="dropzone-hint">
                <span className="empty-icon" aria-hidden>
                  📷
                </span>
                <strong>Take or choose a photo</strong>
                <span className="muted small">or drag one here</span>
              </span>
            )}
          </label>
          <div className="row gap-sm">
            <button
              className="btn btn-primary"
              disabled={!file || analyze.busy || result !== null}
              onClick={() => file && analyze.run(file)}
            >
              {analyze.busy ? "Analyzing…" : "Analyze photo"}
            </button>
            {file && (
              <button className="btn btn-ghost" onClick={reset} disabled={analyze.busy}>
                {result ? "Log another" : "Clear"}
              </button>
            )}
          </div>
          {analyze.busy && (
            <p className="muted small">This usually takes 5–15 seconds.</p>
          )}
          <ErrorNote message={analyze.error} />
        </Card>

        <Card title="Result">
          {!result && (
            <p className="muted">
              The foods found in your photo will show up here. Eating today's office meal? Log
              it from the <Link to="/menu">office menu</Link> instead — no photo needed.
            </p>
          )}
          {result && (
            <div className="stack">
              {result.is_duplicate && (
                <p className="note">
                  You uploaded this photo recently, so here's the earlier analysis. It wasn't
                  logged twice.
                </p>
              )}
              <div className="stat-big">{kcal(result.total_calories)}</div>
              <MealItems items={result.items} />
              <Warnings warnings={result.warnings} />
              <Link to={`/meals/${result.meal_id}`} className="link small">
                View in meal history →
              </Link>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
