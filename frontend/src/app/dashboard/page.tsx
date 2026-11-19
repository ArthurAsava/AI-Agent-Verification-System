"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AppHeader from "@/components/AppHeader";
import {
  AgentApiError,
  type AgentProfile,
  type AgentRegistration,
  getMyAgentProfile,
  registerAgent,
  updateMyAgentProfile,
} from "@/lib/agent-api";
import { createClient } from "@/lib/supabase/client";

type ProfileForm = AgentRegistration;

const EMPTY_PROFILE: ProfileForm = {
  first_name: "",
  last_name: "",
  phone_number: "",
  date_of_birth: "",
  primary_residence: "",
  nationality: "",
  avatar_variant: "male",
};

function ageFromDateOfBirth(value: string): string {
  if (!value) return "Add your date of birth first.";

  const dateOfBirth = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dateOfBirth.getTime())) return "Enter a valid date.";

  const today = new Date();
  let age = today.getFullYear() - dateOfBirth.getFullYear();
  const birthdayStillAhead =
    today.getMonth() < dateOfBirth.getMonth() ||
    (today.getMonth() === dateOfBirth.getMonth() &&
      today.getDate() < dateOfBirth.getDate());

  if (birthdayStillAhead) age -= 1;
  return age >= 0 ? `${age} years old` : "Enter a past date.";
}

function profileNeedsIdentityDetails(profile: AgentProfile): boolean {
  return !(
    profile.first_name &&
    profile.last_name &&
    profile.date_of_birth &&
    profile.primary_residence &&
    profile.nationality &&
    profile.avatar_variant
  );
}

function formFromProfile(profile: AgentProfile): ProfileForm {
  return {
    first_name: profile.first_name,
    last_name: profile.last_name,
    phone_number: profile.phone_number ?? "",
    date_of_birth: profile.date_of_birth ?? "",
    primary_residence: profile.primary_residence ?? "",
    nationality: profile.nationality ?? "",
    avatar_variant: profile.avatar_variant ?? "male",
  };
}

function statusCopy(status: string): string {
  switch (status) {
    case "under_review":
      return "Your profile is being reviewed. We will update your status when the verification team has completed its assessment.";
    case "approved":
      return "Your profile has been approved.";
    case "rejected":
      return "Your profile needs attention before it can be approved.";
    case "suspended":
      return "Your profile is currently unavailable. Please contact support.";
    default:
      return "Your identity details are ready. Continue to documents when you are ready.";
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<AgentProfile | null>(null);
  const [form, setForm] = useState<ProfileForm>(EMPTY_PROFILE);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

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
        if (!active) return;

        setProfile(agent);
        setForm(formFromProfile(agent));
      } catch (error) {
        if (!active) return;

        if (error instanceof AgentApiError && error.status === 404) {
          setProfile(null);
          setForm(EMPTY_PROFILE);
        } else if (error instanceof AgentApiError && error.status === 401) {
          router.replace("/login");
        } else {
          setMessage(
            error instanceof Error
              ? error.message
              : "Unable to load your profile.",
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

  async function handleProfileSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setSaving(true);

    try {
      const payload: AgentRegistration = {
        ...form,
        phone_number: form.phone_number?.trim() || null,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        primary_residence: form.primary_residence.trim(),
        nationality: form.nationality.trim(),
      };
      const saved = profile
        ? await updateMyAgentProfile(payload)
        : await registerAgent(payload);

      setProfile(saved);
      router.push("/documents");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "We could not save your profile.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleLogout() {
    const supabase = createClient();
    const { error } = await supabase.auth.signOut({ scope: "local" });

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
        <AppHeader authenticatedHref="/" authenticatedLabel="Home" />
        <div className="app-content">
          <p className="app-eyebrow">Agent workspace</p>
          <h1 className="app-title">Preparing your profile.</h1>
        </div>
      </main>
    );
  }

  const needsIdentityDetails = !profile || profileNeedsIdentityDetails(profile);

  return (
    <main className="app-page">
      <AppHeader authenticatedHref="/" authenticatedLabel="Home" />
      <div className="app-content workspace-stack">
        <header className="workspace-heading">
          <div>
            <p className="app-eyebrow">Agent workspace</p>
            <h1 className="app-title">Your profile, in motion.</h1>
            <p className="app-subtitle">
              Complete one clear step at a time to submit your identity for review.
            </p>
          </div>
        </header>

        <div className="app-toolbar">
          <p className="status-message" role="status">{message}</p>
          <button className="button button--dark" onClick={() => void handleLogout()}>
            Log out
          </button>
        </div>

        {needsIdentityDetails ? (
          <section className="app-panel" aria-labelledby="identity-details-heading">
            <p className="app-eyebrow">Step 1 of 3</p>
            <h2 id="identity-details-heading">Tell us about yourself.</h2>
            <p>These details must match the identity document you submit next.</p>

            <form className="auth-form" onSubmit={handleProfileSubmit}>
              <div className="auth-field">
                <label htmlFor="first-name">First name</label>
                <input id="first-name" required minLength={2} maxLength={100} value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} disabled={saving} />
              </div>

              <div className="auth-field">
                <label htmlFor="last-name">Last name</label>
                <input id="last-name" required minLength={2} maxLength={100} value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} disabled={saving} />
              </div>

              <div className="auth-field">
                <label htmlFor="date-of-birth">Date of birth</label>
                <input id="date-of-birth" type="date" required value={form.date_of_birth} onChange={(event) => setForm({ ...form, date_of_birth: event.target.value })} disabled={saving} />
                <small>Age: {ageFromDateOfBirth(form.date_of_birth)}</small>
              </div>

              <div className="auth-field">
                <label htmlFor="sex">Sex</label>
                <select id="sex" required value={form.avatar_variant} onChange={(event) => setForm({ ...form, avatar_variant: event.target.value as "male" | "female" })} disabled={saving}>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </div>

              <div className="auth-field">
                <label htmlFor="primary-residence">Primary residence</label>
                <input id="primary-residence" required minLength={2} maxLength={255} autoComplete="address-level2" value={form.primary_residence} onChange={(event) => setForm({ ...form, primary_residence: event.target.value })} disabled={saving} />
              </div>

              <div className="auth-field">
                <label htmlFor="nationality">Nationality</label>
                <input id="nationality" required minLength={2} maxLength={100} autoComplete="country-name" value={form.nationality} onChange={(event) => setForm({ ...form, nationality: event.target.value })} disabled={saving} />
              </div>

              <div className="auth-field">
                <label htmlFor="phone">Phone number <span>(optional)</span></label>
                <input id="phone" type="tel" autoComplete="tel" value={form.phone_number ?? ""} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} disabled={saving} />
              </div>

              <button className="button button--dark" type="submit" disabled={saving}>
                {saving ? "Saving your details..." : "Save and continue to documents"}
              </button>
            </form>
          </section>
        ) : (
          <section className="app-panel" aria-labelledby="profile-status-heading">
            <p className="app-eyebrow">Profile status</p>
            <h2 id="profile-status-heading">
              {profile.status === "under_review" ? "Your profile is being reviewed." : "Your profile is ready."}
            </h2>
            <p>{statusCopy(profile.status)}</p>
            <p><strong>{profile.first_name} {profile.last_name}</strong>{" · "}{profile.nationality}</p>

            {profile.status === "pending" && (
              <Link className="button button--gold" href="/documents">
                Continue to documents <span aria-hidden="true">→</span>
              </Link>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
