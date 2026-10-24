import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorNote } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useAction } from "../lib/hooks";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { run, busy, error } = useAction(login);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if ((await run(email, password)).ok) navigate("/", { replace: true });
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand brand-lg">
          <span aria-hidden>🥗</span> Food Agent
        </div>
        <h1>Welcome back</h1>
        <p className="muted">Log in to track meals, water and get suggestions.</p>

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        <ErrorNote message={error} />
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
        <p className="muted small center">
          New here? <Link to="/signup">Create an account</Link>
        </p>
      </form>
    </div>
  );
}
