
"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { loginErrorMessage } from "@/lib/auth-error-messages";
import AuthFrame from "@/components/AuthFrame";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMessage("");

    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        setErrorMessage(loginErrorMessage(error));
        return;
      }

      router.push("/dashboard");
      router.refresh();
    } catch (error) {
      setErrorMessage(loginErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleSignIn() {
    setGoogleLoading(true);
    setErrorMessage("");

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: new URL(
          "/auth/confirm?next=/dashboard",
          window.location.origin,
        ).toString(),
      },
    });

    if (error) {
      setErrorMessage(error.message);
      setGoogleLoading(false);
    }
  }

  return (
    <AuthFrame
      eyebrow="Welcome back"
      title="Continue your journey."
      description="Sign in to view your profile, finish verification, and follow every next step."
    >
      <form className="auth-form" onSubmit={handleLogin}>
        <div className="auth-field">
          <label htmlFor="email">Email address</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={loading || googleLoading}
          />
        </div>

        <div className="auth-field">
          <label htmlFor="password">Password</label>
          <div className="password-input">
            <input
              id="password"
              type={passwordVisible ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading || googleLoading}
            />
            <button
              className="password-input__toggle"
              type="button"
              aria-label={passwordVisible ? "Hide password" : "Show password"}
              aria-pressed={passwordVisible}
              onClick={() => setPasswordVisible((visible) => !visible)}
              disabled={loading || googleLoading}
            >
              {passwordVisible ? "Hide" : "Show"}
            </button>
          </div>
        </div>

        <button
          className="button button--dark"
          disabled={loading || googleLoading}
          type="submit"
        >
          {loading ? "Signing you in..." : "Log in to Verity"}
        </button>
      </form>

      <div className="auth-divider" aria-hidden="true">
        <span>or</span>
      </div>

      <button
        className="auth-google-button"
        type="button"
        onClick={() => void handleGoogleSignIn()}
        disabled={loading || googleLoading}
      >
        <span className="auth-google-button__mark" aria-hidden="true">G</span>
        {googleLoading ? "Opening Google..." : "Continue with Google"}
      </button>

      <p
        className={`auth-message${errorMessage ? " auth-message--error" : ""}`}
        role="alert"
      >
        {errorMessage}
      </p>
      <p className="auth-switch">
        New to Verity? <Link href="/signup">Create your account</Link>
      </p>
    </AuthFrame>
  );
}
