
"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import {
  signupErrorMessage,
  signupReturnedExistingAccount,
} from "@/lib/auth-error-messages";
import AuthFrame from "@/components/AuthFrame";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [confirmPasswordVisible, setConfirmPasswordVisible] = useState(false);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  async function handleSignup(e: FormEvent) {
    e.preventDefault();
    setMessage("");
    setErrorMessage("");

    if (password !== confirmPassword) {
      setErrorMessage("Your passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const supabase = createClient();
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo:
            new URL(
              "/auth/confirm?next=/dashboard",
              window.location.origin,
            ).toString(),
        },
      });

      if (error) {
        setErrorMessage(signupErrorMessage(error));
      } else if (signupReturnedExistingAccount(data.user)) {
        setErrorMessage(
          "An account is already registered with this email. Please log in instead.",
        );
      } else {
        setMessage(
          "Check your email to confirm your account. We will take you straight to profile registration.",
        );
      }
    } catch (error) {
      setErrorMessage(signupErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleSignIn() {
    setGoogleLoading(true);
    setMessage("");
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
      eyebrow="Create your profile"
      title="Start with a trusted identity."
      description="Set up your secure Verity account. We will guide you through the verification details after confirmation."
    >
      <form className="auth-form" onSubmit={handleSignup}>
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
          <label htmlFor="password">Create a password</label>
          <div className="password-input">
            <input
              id="password"
              type={passwordVisible ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={12}
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

        <div className="auth-field">
          <label htmlFor="confirm-password">Confirm your password</label>
          <div className="password-input">
            <input
              id="confirm-password"
              type={confirmPasswordVisible ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={12}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={loading || googleLoading}
            />
            <button
              className="password-input__toggle"
              type="button"
              aria-label={
                confirmPasswordVisible
                  ? "Hide confirmed password"
                  : "Show confirmed password"
              }
              aria-pressed={confirmPasswordVisible}
              onClick={() =>
                setConfirmPasswordVisible((visible) => !visible)
              }
              disabled={loading || googleLoading}
            >
              {confirmPasswordVisible ? "Hide" : "Show"}
            </button>
          </div>
        </div>

        <button
          className="button button--dark"
          disabled={loading || googleLoading}
          type="submit"
        >
          {loading ? "Creating your account..." : "Create account"}
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
        role={errorMessage ? "alert" : "status"}
      >
        {errorMessage || message}
      </p>
      <p className="auth-switch">
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </AuthFrame>
  );
}
