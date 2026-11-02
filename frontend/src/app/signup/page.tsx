
"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

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
          `${window.location.origin}/login`,
      },
    });

    setMessage(
      error
        ? error.message
        : "Check your email to confirm your account, then sign in."
    );

    setLoading(false);
  }

  return (
    <main style={{ maxWidth: 420, margin: "60px auto" }}>
      <h1>Create Agent Account</h1>
      <p>Register for SalesMesh agent verification.</p>

      <form onSubmit={handleSignup}>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          required
          minLength={12}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button disabled={loading} type="submit">
          {loading ? "Creating..." : "Sign up"}
        </button>
      </form>

      <p role="status">{message}</p>
      <p>
        Already registered? <Link href="/login">Log in</Link>
      </p>
    </main>
  );
}
