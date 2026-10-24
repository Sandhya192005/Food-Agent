import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError, DATA_CHANGED } from "./api";

interface Query<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/** GETs `path` on mount (and whenever it changes), and refetches when other
 *  parts of the app report a data change. Pass null to skip fetching. */
export function useQuery<T>(path: string | null): Query<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const requestId = useRef(0);

  const load = useCallback(() => {
    if (path === null) return;
    const id = ++requestId.current;
    setLoading(true);
    api<T>(path)
      .then((result) => {
        if (id !== requestId.current) return; // a newer request superseded this one
        setData(result);
        setError(null);
      })
      .catch((err: ApiError) => {
        if (id !== requestId.current) return;
        setData(null);
        setError(err);
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
  }, [path]);

  useEffect(() => {
    load();
    window.addEventListener(DATA_CHANGED, load);
    return () => window.removeEventListener(DATA_CHANGED, load);
  }, [load]);

  return { data, error, loading, reload: load };
}

type ActionResult<R> = { ok: true; value: R } | { ok: false };

/** Wraps a one-off action (POST/PATCH/DELETE) with busy and error state. */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (...args: A): Promise<ActionResult<R>> => {
      setBusy(true);
      setError(null);
      try {
        return { ok: true, value: await fn(...args) };
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong");
        return { ok: false };
      } finally {
        setBusy(false);
      }
    },
    [fn],
  );

  return { run, busy, error, setError };
}
