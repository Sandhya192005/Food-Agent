import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { api, notifyDataChanged } from "../lib/api";
import { timeAgo } from "../lib/format";
import type { AppNotification } from "../lib/types";

const POLL_MS = 30_000;

const ICON: Record<string, string> = { water_check: "💧", meal_nudge: "🍽️" };
const TITLE: Record<string, string> = { water_check: "Water check", meal_nudge: "Snack idea" };

/** Shows the water and meal agents' pending reminders: a bell with a count,
 *  a panel listing them, and a pop-up toast when a new one arrives. */
export function NotificationCenter() {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [open, setOpen] = useState(false);
  const [toasts, setToasts] = useState<AppNotification[]>([]);
  const [answering, setAnswering] = useState<number | null>(null);
  const seen = useRef<Set<number> | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const poll = useCallback(async () => {
    try {
      const pending = await api<AppNotification[]>("/notifications/pending");
      setItems(pending);
      // Don't toast everything that was already waiting on first load.
      if (seen.current === null) {
        seen.current = new Set(pending.map((n) => n.id));
        return;
      }
      const fresh = pending.filter((n) => !seen.current!.has(n.id));
      fresh.forEach((n) => seen.current!.add(n.id));
      if (fresh.length) setToasts((t) => [...t, ...fresh]);
    } catch {
      /* a missed poll is fine; try again next tick */
    }
  }, []);

  useEffect(() => {
    poll();
    const timer = window.setInterval(poll, POLL_MS);
    const onFocus = () => poll();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [poll]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!panelRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function respond(n: AppNotification, response: "yes" | "no") {
    setAnswering(n.id);
    try {
      await api(`/notifications/${n.id}/respond`, { method: "POST", json: { response } });
    } catch {
      /* already answered elsewhere (e.g. the desktop watcher) — just drop it */
    }
    setItems((list) => list.filter((x) => x.id !== n.id));
    setToasts((list) => list.filter((x) => x.id !== n.id));
    setAnswering(null);
    if (response === "yes") notifyDataChanged(); // "Yes" on water logs 250 ml
  }

  const renderItem = (n: AppNotification, compact = false) => (
    <div className={compact ? "notif notif-toast" : "notif"} key={n.id}>
      <span className="notif-icon" aria-hidden>
        {ICON[n.type] ?? "🔔"}
      </span>
      <div className="notif-body">
        <div className="notif-title">
          <strong>{TITLE[n.type] ?? "Reminder"}</strong>
          <span className="muted small">{timeAgo(n.created_at)}</span>
        </div>
        <p>{n.message}</p>
        <div className="row gap-sm">
          <button
            className="btn btn-primary btn-sm"
            disabled={answering === n.id}
            onClick={() => respond(n, "yes")}
          >
            {n.type === "water_check" ? "Yes, log 250 ml" : "Yes"}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            disabled={answering === n.id}
            onClick={() => respond(n, "no")}
          >
            {n.type === "water_check" ? "Not yet" : "No"}
          </button>
        </div>
      </div>
      {compact && (
        <button
          className="icon-btn"
          aria-label="Dismiss"
          onClick={() => setToasts((list) => list.filter((x) => x.id !== n.id))}
        >
          ✕
        </button>
      )}
    </div>
  );

  return (
    <>
      <div className="notif-anchor" ref={panelRef}>
        <button
          className="icon-btn bell"
          aria-label={`Notifications (${items.length} pending)`}
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        >
          🔔
          {items.length > 0 && <span className="badge">{items.length}</span>}
        </button>
        {open && (
          <div className="notif-panel" role="dialog" aria-label="Notifications">
            <h3>Reminders</h3>
            {items.length === 0 ? (
              <p className="muted small">You're all caught up.</p>
            ) : (
              items.map((n) => renderItem(n))
            )}
          </div>
        )}
      </div>
      {/* Portal: the top bar's backdrop blur would otherwise pin these to the top bar. */}
      {createPortal(
        <div className="toast-stack" aria-live="polite">
          {toasts.map((n) => renderItem(n, true))}
        </div>,
        document.body,
      )}
    </>
  );
}
