import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { EMPTY_PROFILE, ProfileFieldset } from "../components/ProfileForm";
import { ErrorNote } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useAction } from "../lib/hooks";
import type { ProfileFields } from "../lib/types";

export function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [profile, setProfile] = useState<ProfileFields>(EMPTY_PROFILE);
  const { run, busy, error } = useAction(signup);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if ((await run({ email, password, ...profile })).ok) navigate("/", { replace: true });
  }

  return (
    <div className="auth-page">
      <form className="auth-card auth-card-wide" onSubmit={submit}>
        <div className="brand brand-lg">
          <span aria-hidden>🥗</span> Food Agent
        </div>
        <h1>Create your account</h1>
        <p className="muted">
          Your details are used to work out calorie, protein and water targets.
        </p>

        <fieldset>
          <legend>Account</legend>
          <div className="grid-2">
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
              <span>Password (8+ characters)</span>
              <input
                type="password"
                required
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
          </div>
        </fieldset>

        <ProfileFieldset value={profile} onChange={setProfile} />

        <ErrorNote message={error} />
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="muted small center">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
