
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
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
    return <main><p>Loading dashboard...</p></main>;
  }

  return (
    <main style={{ maxWidth: 650, margin: "50px auto" }}>
      <h1>SalesMesh Agent Dashboard</h1>

      <button onClick={handleLogout}>
        Log out
      </button>

      <p role="status">{message}</p>

      {needsRegistration && (
        <form onSubmit={handleRegistration}>
          <h2>Complete Agent Registration</h2>

          <input
            aria-label="First name"
            placeholder="First name"
            required
            minLength={2}
            value={firstName}
            onChange={(e) =>
              setFirstName(e.target.value)
            }
          />

          <input
            aria-label="Last name"
            placeholder="Last name"
            required
            minLength={2}
            value={lastName}
            onChange={(e) =>
              setLastName(e.target.value)
            }
          />

          <input
            aria-label="Phone number"
            placeholder="Phone number (optional)"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />

          <button type="submit">
            Complete registration
          </button>
        </form>
      )}

      
{profile && (
  <section>
    <h2>My Profile</h2>

    <p>
      Name: {profile.first_name}{" "}
      {profile.last_name}
    </p>

    <p>
      Status: {profile.status}
    </p>

    <p>
      Phone: {profile.phone_number ?? "Not provided"}
    </p>

    {/* Phase 6: Agent Onboarding */}
    <div style={{ marginTop: "24px" }}>
      <h3>Agent Onboarding</h3>

      <p>
        Complete your personal information,
        provide your sales background, and
        prepare for identity verification.
      </p>

      <Link
        href="/onboarding"
        style={{
          display: "inline-block",
          marginTop: "12px",
          padding: "12px 20px",
          backgroundColor: "#2563eb",
          color: "#ffffff",
          borderRadius: "8px",
          textDecoration: "none",
          fontWeight: 600,
        }}
      >
        Continue Onboarding →
      </Link>
    </div>
  </section>
)}


    </main>
  );
}
