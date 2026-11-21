"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AppHeader from "@/components/AppHeader";
import { useAuthSession } from "@/components/AuthSessionProvider";
import {
  deleteMyAccount,
  getAccountDeletionEligibility,
  getMyAccountSessions,
  type AccountSession,
  SessionApiError,
} from "@/lib/session-api";
import { createClient } from "@/lib/supabase/client";

function formatDateTime(value: string | null) {
  if (!value) return "Not available";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function deviceLabel(session: AccountSession) {
  if (session.is_current) return "This browser";
  return session.user_agent?.trim() || "Another signed-in browser or device";
}

export default function SecurityPage() {
  const router = useRouter();
  const { isLoading: sessionLoading, session, user } = useAuthSession();
  const [sessions, setSessions] = useState<AccountSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [message, setMessage] = useState("");
  const [revokingOthers, setRevokingOthers] = useState(false);
  const [canDeleteAccount, setCanDeleteAccount] = useState(false);
  const [deletionFormOpen, setDeletionFormOpen] = useState(false);
  const [deletionPassword, setDeletionPassword] = useState("");
  const [showDeletionPassword, setShowDeletionPassword] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [deletionError, setDeletionError] = useState("");

  useEffect(() => {
    if (sessionLoading) return;
    if (!session) {
      router.replace("/login");
      return;
    }

    let active = true;

    async function loadSessions() {
      setLoadingSessions(true);
      setMessage("");

      const [sessionsResult, eligibilityResult] = await Promise.allSettled([
        getMyAccountSessions(),
        getAccountDeletionEligibility(),
      ]);

      if (!active) return;

      if (sessionsResult.status === "fulfilled") {
        setSessions(sessionsResult.value);
      } else {
        const error = sessionsResult.reason;

        if (error instanceof SessionApiError && error.status === 401) {
          router.replace("/login");
          return;
        }

        setMessage(
          error instanceof Error
            ? error.message
            : "We could not load your account sessions.",
        );
      }

      if (eligibilityResult.status === "fulfilled") {
        setCanDeleteAccount(eligibilityResult.value.eligible);
      } else {
        const error = eligibilityResult.reason;

        if (error instanceof SessionApiError && error.status === 401) {
          router.replace("/login");
          return;
        }
      }

      if (active) setLoadingSessions(false);
    }

    void loadSessions();

    return () => {
      active = false;
    };
  }, [router, session, sessionLoading]);

  async function signOutOtherSessions() {
    setMessage("");
    setRevokingOthers(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signOut({ scope: "others" });

    if (error) {
      setMessage(error.message);
      setRevokingOthers(false);
      return;
    }

    setSessions((current) => current.filter((item) => item.is_current));
    setMessage("Other active sessions have been signed out.");
    setRevokingOthers(false);
  }

  async function deleteAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDeletionError("");

    if (!deletionPassword) {
      setDeletionError("Enter your password to delete this account.");
      return;
    }

    setDeletingAccount(true);

    try {
      await deleteMyAccount(deletionPassword);

      // The backend has already revoked every Auth session. A local sign-out
      // clears this browser's cached session before returning to the homepage.
      const supabase = createClient();
      await supabase.auth.signOut({ scope: "local" });
      router.replace("/");
      router.refresh();
    } catch (error) {
      if (error instanceof SessionApiError && error.status === 401) {
        setDeletionError("Your password is incorrect.");
      } else if (error instanceof SessionApiError && error.status === 429) {
        setDeletionError("Too many attempts. Please wait before trying again.");
      } else {
        setDeletionError(
          error instanceof Error
            ? error.message
            : "Your account could not be deleted. Please try again.",
        );
      }
      setDeletingAccount(false);
    }
  }

  if (sessionLoading || !session) {
    return (
      <main className="app-page">
        <AppHeader authenticatedHref="/" authenticatedLabel="Home" />
        <div className="app-content">
          <p className="app-eyebrow">Account security</p>
          <h1 className="app-title">Checking your session.</h1>
        </div>
      </main>
    );
  }

  const expiresAt = session.expires_at
    ? new Date(session.expires_at * 1_000).toISOString()
    : null;
  const otherSessionCount = sessions.filter((item) => !item.is_current).length;

  return (
    <main className="app-page">
      <AppHeader authenticatedHref="/" authenticatedLabel="Home" />
      <div className="app-content workspace-stack security-page">
        <header className="workspace-heading">
          <div>
            <p className="app-eyebrow">Account security</p>
            <h1 className="app-title">Your signed-in sessions.</h1>
            <p className="app-subtitle">
              Review where your account is active and end any other active
              sessions if something does not look familiar.
            </p>
          </div>
        </header>

        <section className="app-panel security-current-session" aria-labelledby="current-session-heading">
          <div>
            <p className="app-eyebrow">Current session</p>
            <h2 id="current-session-heading">Signed in on this browser</h2>
            <p>{user?.email ?? "Your verified Verity account"}</p>
          </div>
          <span className="security-status" role="status">
            <span aria-hidden="true" /> Active
          </span>
          <dl className="security-details-grid">
            <div>
              <dt>Session refreshes until</dt>
              <dd>{formatDateTime(expiresAt)}</dd>
            </div>
            <div>
              <dt>Account last signed in</dt>
              <dd>{formatDateTime(user?.last_sign_in_at ?? null)}</dd>
            </div>
          </dl>
        </section>

        <section className="app-panel" aria-labelledby="sessions-heading">
          <div className="profile-summary__heading">
            <div>
              <p className="app-eyebrow">Session tracker</p>
              <h2 id="sessions-heading">Your account sessions</h2>
            </div>
            <button
              className="button button--gold"
              type="button"
              onClick={() => void signOutOtherSessions()}
              disabled={revokingOthers || loadingSessions || otherSessionCount === 0}
            >
              {revokingOthers
                ? "Signing out…"
                : otherSessionCount > 0
                  ? "Sign out other sessions"
                  : "No other sessions"}
            </button>
          </div>
          <p>
            Only your own session records are shown here. Network addresses,
            refresh tokens, and other sensitive credentials are never exposed.
          </p>

          {message && <p className="status-message" role="status">{message}</p>}

          {loadingSessions ? (
            <p className="security-empty">Loading your account sessions…</p>
          ) : sessions.length > 0 ? (
            <ul className="security-session-list">
              {sessions.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{deviceLabel(item)}</strong>
                    <span>
                      Last active {formatDateTime(item.last_active_at)}
                    </span>
                  </div>
                  {item.is_current && <em>Current</em>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="security-empty">
              Your current browser session is active. No additional session
              records are available yet.
            </p>
          )}
        </section>

        <section className="app-panel security-help" aria-labelledby="security-help-heading">
          <p className="app-eyebrow">Need to leave this browser?</p>
          <h2 id="security-help-heading">Sign out when you are finished.</h2>
          <p>
            Use the account menu in the header to sign out of this browser.
            You can always return to your workspace after signing in again.
          </p>
          <Link className="button button--dark" href="/dashboard">
            Back to dashboard
          </Link>
        </section>

        {canDeleteAccount && (
          <section
            className="app-panel security-delete-account"
            aria-labelledby="delete-account-heading"
          >
            <p className="app-eyebrow">Danger zone</p>
            <h2 id="delete-account-heading">Delete your account</h2>
            <p>
              This permanently removes your Verity profile, verification
              records, uploaded identity documents, and active sessions. This
              action cannot be undone.
            </p>

            {!deletionFormOpen ? (
              <button
                className="button button--danger"
                type="button"
                onClick={() => {
                  setDeletionError("");
                  setDeletionFormOpen(true);
                }}
              >
                Delete account
              </button>
            ) : (
              <form className="security-delete-form" onSubmit={deleteAccount}>
                <label htmlFor="delete-account-password">
                  Confirm with your password
                  <span className="password-input">
                    <input
                      id="delete-account-password"
                      type={showDeletionPassword ? "text" : "password"}
                      value={deletionPassword}
                      onChange={(event) => setDeletionPassword(event.target.value)}
                      autoComplete="current-password"
                      disabled={deletingAccount}
                      required
                    />
                    <button
                      className="password-input__toggle"
                      type="button"
                      onClick={() => setShowDeletionPassword((visible) => !visible)}
                      disabled={deletingAccount}
                      aria-label={showDeletionPassword ? "Hide password" : "Show password"}
                    >
                      {showDeletionPassword ? "Hide" : "Show"}
                    </button>
                  </span>
                </label>

                {deletionError && (
                  <p className="security-delete-error" role="alert">
                    {deletionError}
                  </p>
                )}

                <div className="security-delete-form__actions">
                  <button
                    className="button button--danger"
                    type="submit"
                    disabled={deletingAccount}
                  >
                    {deletingAccount ? "Deleting account…" : "Permanently delete account"}
                  </button>
                  <button
                    className="button button--dark"
                    type="button"
                    disabled={deletingAccount}
                    onClick={() => {
                      setDeletionFormOpen(false);
                      setDeletionPassword("");
                      setShowDeletionPassword(false);
                      setDeletionError("");
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
