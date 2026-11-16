
"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import AuthFrame from "@/components/AuthFrame";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMessage("");

    const supabase = createClient();

    const { error } =
      await supabase.auth.signInWithPassword({
        email,
        password,
      });

    if (error) {
      setErrorMessage(error.message);
      setLoading(false);
      return;
    }

    router.push("/dashboard");
    router.refresh();
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
          />
        </div>

        <div className="auth-field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <button className="button button--dark" disabled={loading} type="submit">
          {loading ? "Signing you in..." : "Log in to SalesMesh"}
        </button>
      </form>

      <p
        className={`auth-message${errorMessage ? " auth-message--error" : ""}`}
        role="alert"
      >
        {errorMessage}
      </p>
      <p className="auth-switch">
        New to SalesMesh? <Link href="/signup">Create your account</Link>
      </p>
    </AuthFrame>
  );
}
