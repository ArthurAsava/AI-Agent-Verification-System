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

type ProfileForm = Omit<AgentRegistration, "avatar_variant"> & {
  avatar_variant: AgentRegistration["avatar_variant"] | "";
};

const EMPTY_PROFILE: ProfileForm = {
  first_name: "",
  last_name: "",
  phone_number: "",
  date_of_birth: "",
  primary_residence: "",
  nationality: "",
  avatar_variant: "",
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
    avatar_variant: profile.avatar_variant ?? "",
  };
}

function formatDate(value: string | null): string {
  if (!value) return "Not provided";

  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

function statusCopy(status: string): string {
  switch (status) {
    case "under_review":
      return "Your profile is being reviewed. We will update your status when the verification team has completed its assessment.";
    case "approved":
      return "Your profile has been approved.";
    case "rejected":
      return "Your profile was rejected. Review the feedback from Verity before submitting again.";
    case "suspended":
      return "Your profile is currently unavailable. Please contact support.";
    default:
      return "Your identity details are ready. Continue to documents when you are ready.";
  }
}

function statusHeading(status: string): string {
  switch (status) {
    case "under_review":
      return "Your profile is being reviewed.";
    case "approved":
      return "Your profile has been approved.";
    case "rejected":
      return "Your profile was rejected.";
    case "suspended":
      return "Your profile is unavailable.";
    default:
      return "Your profile is ready.";
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<AgentProfile | null>(null);
  const [form, setForm] = useState<ProfileForm>(EMPTY_PROFILE);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingProfile, setEditingProfile] = useState(false);
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

    const avatarVariant = form.avatar_variant;
    if (
      avatarVariant !== "male" &&
      avatarVariant !== "female"
    ) {
      setMessage("Select the sex recorded on your identity document.");
      return;
    }

    setSaving(true);

    try {
      const payload: AgentRegistration = {
        ...form,
        avatar_variant: avatarVariant,
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
      setForm(formFromProfile(saved));
      setEditingProfile(false);
      setMessage("Your details have been saved.");
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
  const showProfileForm = needsIdentityDetails || editingProfile;

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

        {showProfileForm ? (
          <section className="app-panel" aria-labelledby="identity-details-heading">
            <p className="app-eyebrow">Step 1 of 3</p>
            <h2 id="identity-details-heading">
              {editingProfile ? "Edit your details." : "Tell us about yourself."}
            </h2>
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
                  <option value="" disabled>Select the sex on your identity document</option>
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
                {saving
                  ? "Saving your details..."
                  : editingProfile
                    ? "Save changes"
                    : "Save details"}
              </button>
              {editingProfile && profile && (
                <button
                  className="button button--gold"
                  type="button"
                  disabled={saving}
                  onClick={() => {
                    setForm(formFromProfile(profile));
                    setEditingProfile(false);
                    setMessage("");
                  }}
                >
                  Cancel
                </button>
              )}
            </form>
          </section>
        ) : (
          <>
            <section className="app-panel profile-summary" aria-labelledby="profile-details-heading">
              <div className="profile-summary__heading">
                <div>
                  <p className="app-eyebrow">Your details</p>
                  <h2 id="profile-details-heading">
                    {profile.first_name} {profile.last_name}
                  </h2>
                </div>
                <button
                  className="button button--gold"
                  type="button"
                  onClick={() => {
                    setForm(formFromProfile(profile));
                    setEditingProfile(true);
                    setMessage("");
                  }}
                >
                  Edit
                </button>
              </div>

              <dl className="profile-details-grid">
                <div><dt>First name</dt><dd>{profile.first_name}</dd></div>
                <div><dt>Last name</dt><dd>{profile.last_name}</dd></div>
                <div><dt>Date of birth</dt><dd>{formatDate(profile.date_of_birth)}</dd></div>
                <div><dt>Age</dt><dd>{ageFromDateOfBirth(profile.date_of_birth ?? "")}</dd></div>
                <div><dt>Sex</dt><dd>{profile.avatar_variant === "female" ? "Female" : "Male"}</dd></div>
                <div><dt>Primary residence</dt><dd>{profile.primary_residence}</dd></div>
                <div><dt>Nationality</dt><dd>{profile.nationality}</dd></div>
                <div><dt>Phone number</dt><dd>{profile.phone_number || "Not provided"}</dd></div>
              </dl>
            </section>

            <section className="app-panel" aria-labelledby="profile-status-heading">
              <p className="app-eyebrow">Profile status</p>
              <h2 id="profile-status-heading">
                {statusHeading(profile.status)}
              </h2>
              <p>{statusCopy(profile.status)}</p>

              {profile.status === "pending" && (
                <Link className="button button--gold" href="/documents">
                  Continue to documents <span aria-hidden="true">→</span>
                </Link>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
