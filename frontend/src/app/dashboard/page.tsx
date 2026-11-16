
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import AppHeader from "@/components/AppHeader";
import {
  AgentProfile,
  getMyAgentProfile,
  registerAgent,
} from "@/lib/agent-api";

export default function DashboardPage() {
  const router = useRouter();

  const [profile, setProfile] =
    useState<AgentProfile | null>(null);
  const [needsRegistration, setNeedsRegistration] =
    useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function loadProfile() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();

      if (!active) return;

      if (!data.session) {
        router.replace("/login");
        return;
      }

      try {
        const agent = await getMyAgentProfile();
        if (active) setProfile(agent);
      } catch (error) {
        if (!active) return;

        if (
          error instanceof Error &&
          error.message === "Agent profile not found"
        ) {
          setNeedsRegistration(true);
        } else {
          setMessage(
            error instanceof Error
              ? error.message
              : "Unable to load profile"
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadProfile();

    return () => {
      active = false;
    };
  }, [router]);

  async function handleRegistration(
    e: React.FormEvent
  ) {
    e.preventDefault();
    setMessage("");

    try {
      const agent = await registerAgent({
        first_name: firstName,
        last_name: lastName,
        phone_number: phone || null,
      });

      setProfile(agent);
      setNeedsRegistration(false);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Registration failed"
      );
    }
  }

  async function handleLogout() {
    const supabase = createClient();

    const { error } = await supabase.auth.signOut({
      scope: "local",
    });

    if (error) {
      setMessage(error.message);
      return;
    }

    router.replace("/login");
    router.refresh();
  }

  if (loading) {
    return (
      <main className="app-page">
        <AppHeader />
        <div className="app-content">
          <p className="app-eyebrow">Preparing your workspace</p>
          <h1 className="app-title">Loading your profile.</h1>
        </div>
      </main>
    );
  }

  return (
    <main className="app-page">
      <AppHeader />
      <div className="app-content">
        <p className="app-eyebrow">Agent workspace</p>
        <h1 className="app-title">Your profile, in motion.</h1>
        <p className="app-subtitle">
          Everything you need to move your SalesMesh verification forward lives here.
        </p>

        <div className="app-toolbar">
          <p className="status-message" role="status">{message}</p>
          <button className="button button--dark" onClick={handleLogout}>
            Log out
          </button>
        </div>

        {needsRegistration && (
          <section className="app-panel">
            <p className="app-eyebrow">Profile setup</p>
            <h2>Complete your agent profile.</h2>
            <p>Give us the basics, then we will guide you through identity verification.</p>

            <form className="auth-form" onSubmit={handleRegistration}>
              <div className="auth-field">
                <label htmlFor="first-name">First name</label>
                <input
                  id="first-name"
                  required
                  minLength={2}
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                />
              </div>

              <div className="auth-field">
                <label htmlFor="last-name">Last name</label>
                <input
                  id="last-name"
                  required
                  minLength={2}
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                />
              </div>

              <div className="auth-field">
                <label htmlFor="phone">Phone number <span>(optional)</span></label>
                <input
                  id="phone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>

              <button className="button button--dark" type="submit">
                Complete registration
              </button>
            </form>
          </section>
        )}

        {profile && (
          <section className="app-panel">
            <p className="app-eyebrow">My passport profile</p>
            <h2>{profile.first_name} {profile.last_name}</h2>
            <p>Status: {profile.status}</p>
            <p>Phone: {profile.phone_number ?? "Not provided"}</p>

            <div className="app-panel__action">
              <h3>Agent onboarding</h3>
              <p>
                Complete your personal information, provide your sales background,
                and prepare for identity verification.
              </p>
              <Link className="button button--gold" href="/onboarding">
                Continue onboarding <span aria-hidden="true">→</span>
              </Link>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
