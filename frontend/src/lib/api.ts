import type { Tokens } from "./types";

const BASE_URL = "/api/v1";
const ACCESS_KEY = "food-agent.access";
const REFRESH_KEY = "food-agent.refresh";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
  }
}

// --- Token storage (localStorage can throw in private mode, so guard it) ---

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function hasTokens(): boolean {
  return read(ACCESS_KEY) !== null;
}

export function saveTokens(tokens: Tokens): void {
  try {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  } catch {
    /* tokens just won't survive a reload */
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* nothing to clear */
  }
}

export function getRefreshToken(): string | null {
  return read(REFRESH_KEY);
}

// Called when the session can't be recovered; the auth provider sets this.
let onSessionExpired: () => void = () => {};
export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

// --- Refresh: access tokens last 30 min, so renew once on a 401 and retry ---

let refreshInFlight: Promise<boolean> | null = null;

function refreshTokens(): Promise<boolean> {
  const refreshToken = read(REFRESH_KEY);
  if (!refreshToken) return Promise.resolve(false);

  // Several requests can 401 at once; share one refresh call between them.
  refreshInFlight ??= fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
    .then(async (res) => {
      if (!res.ok) return false;
      saveTokens((await res.json()) as Tokens);
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

// --- Request helper ---

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  json?: unknown;
  form?: FormData;
  auth?: boolean;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", json, form, auth = true } = options;

  const send = () => {
    const headers: Record<string, string> = {};
    const token = read(ACCESS_KEY);
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    if (json !== undefined) headers["Content-Type"] = "application/json";
    return fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
    });
  };

  let res: Response;
  try {
    res = await send();
    if (res.status === 401 && auth) {
      if (await refreshTokens()) {
        res = await send();
      }
      if (res.status === 401) {
        clearTokens();
        onSessionExpired();
      }
    }
  } catch {
    throw new ApiError("Can't reach the server. Is the backend running?", 0, "network_error");
  }

  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    // Backend errors look like {"error": {"code": "...", "message": "..."}}.
    const error = body?.error;
    // Validation errors arrive as "body.email: value is not…" — drop the "body." prefix.
    const message = (error?.message as string | undefined)?.replace(/(^|; )body\./g, "$1");
    throw new ApiError(
      message ?? `Request failed (${res.status})`,
      res.status,
      error?.code ?? "unknown_error",
    );
  }
  return body as T;
}

// Pages listen for this to refetch after something changes elsewhere,
// e.g. answering "Yes" on a water notification updates the water card.
export const DATA_CHANGED = "food-agent:data-changed";
export function notifyDataChanged(): void {
  window.dispatchEvent(new Event(DATA_CHANGED));
}
