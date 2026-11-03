import { Card, ErrorNote, Loading, PageHeader } from "../components/ui";
import { WaterCard } from "../components/WaterCard";
import { api, notifyDataChanged } from "../lib/api";
import { useUser } from "../lib/auth";
import { useAction, useQuery } from "../lib/hooks";
import type { WaterReminder } from "../lib/types";

export function Water() {
  const user = useUser();
  const { data, error, loading } = useQuery<WaterReminder>("/water/reminder");
  const snooze = useAction(async () => {
    await api("/water/snooze", { method: "POST" });
    notifyDataChanged();
  });

  return (
    <>
      <PageHeader
        title="Water"
        subtitle={
          user.metrics.daily_water_goal_ml
            ? `Your daily goal is ${(user.metrics.daily_water_goal_ml / 1000).toFixed(1)} L, based on your weight and activity.`
            : undefined
        }
      />
      <div className="two-col">
        <WaterCard showCustom />
        <Card title="⏰ Reminder">
          {loading && !data && <Loading />}
          <ErrorNote message={error?.message} />
          {data && (
            <div className="stack">
              <p>
                Last drink:{" "}
                <strong>
                  {data.minutes_since_last < 60
                    ? `${data.minutes_since_last} min ago`
                    : `${Math.floor(data.minutes_since_last / 60)} h ${data.minutes_since_last % 60} min ago`}
                </strong>
              </p>
              {data.should_remind ? (
                <>
                  <p className="note note-water">{data.message}</p>
                  <button
                    className="btn btn-ghost"
                    disabled={snooze.busy}
                    onClick={() => snooze.run()}
                  >
                    Remind me later
                  </button>
                </>
              ) : (
                <p className="muted">
                  {data.reason === "snoozed"
                    ? "Reminders are snoozed for now."
                    : "You're on track — no reminder needed right now."}
                </p>
              )}
              <ErrorNote message={snooze.error} />
              <p className="muted small">
                The water agent also sends check-ins to the 🔔 bell. Tapping “Yes” there logs 250
                ml for you.
              </p>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
