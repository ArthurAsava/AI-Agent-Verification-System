
"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import AuthFrame from "@/components/AuthFrame";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSignup(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    const supabase = createClient();

    const { error } = await supabase.auth.signUp({
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

    setMessage(
      error
        ? error.message
        : "Check your email to confirm your account. We will take you straight to profile registration."
    );

    setLoading(false);
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
          />
        </div>

        <div className="auth-field">
          <label htmlFor="password">Create a password</label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <button className="button button--dark" disabled={loading} type="submit">
          {loading ? "Creating your account..." : "Create account"}
        </button>
      </form>

      <p className="auth-message" role="status">
        {message}
      </p>
      <p className="auth-switch">
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </AuthFrame>
  );
}
