
"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import KycChecklist from "@/components/KycChecklist";

import OnboardingProgress from
  "@/components/OnboardingProgress";
import AppHeader from "@/components/AppHeader";

import {
  getMyOnboarding,
  updateMyOnboarding,
  OnboardingData,
  OnboardingUpdate,
} from "@/lib/agent-api";


export default function OnboardingPage() {
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [data, setData] =
    useState<OnboardingData | null>(null);

  const [form, setForm] =
    useState<OnboardingUpdate>({});

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const result = await getMyOnboarding();

        if (!active) return;

        setData(result);

        setForm({
          county: result.county ?? "",
          city: result.city ?? "",
          business_name:
            result.business_name ?? "",
          experience_level:
            (result.experience_level as
              OnboardingUpdate["experience_level"])
              ?? null,
          preferred_sales_category:
            result.preferred_sales_category ?? "",
        });
      } catch (error) {
        if (!active) return;

        const detail =
          error instanceof Error
            ? error.message
            : "Unable to load onboarding";

        if (detail === "Please sign in first") {
          router.replace("/login");
        } else if (
          detail === "Complete agent registration first"
        ) {
          router.replace("/dashboard");
        } else {
          setMessage(detail);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [router]);

  async function saveDetails(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage("");

    try {
      const updated =
        await updateMyOnboarding(form);

      setData(updated);
      setStep(3);
      setMessage("Onboarding details saved.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to save details"
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="app-page">
        <AppHeader />
        <div className="app-content">
          <p className="app-eyebrow">Agent onboarding</p>
          <h1 className="app-title">Loading your next step.</h1>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="app-page">
        <AppHeader />
        <div className="app-content">
          <p className="app-eyebrow">Agent onboarding</p>
          <h1 className="app-title">We could not load your profile.</h1>
          <p className="app-subtitle" role="alert">{message}</p>
          <Link className="button button--dark" href="/dashboard">
            Return to dashboard
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="app-page">
      <AppHeader />
      <div className="app-content workspace-stack">
      <header className="workspace-heading">
        <div>
          <p className="app-eyebrow">Agent onboarding</p>
          <h1>Build your passport profile.</h1>
          <p>Three considered steps separate your profile from a trusted verification journey.</p>
        </div>
      </header>

      <section className="app-panel">
        <OnboardingProgress
          percentage={data.progress.percentage}
          completedFields={
            data.progress.completed_fields
          }
          totalFields={data.progress.total_fields}
        />
      </section>

      <p>Step {step} of 3</p>
      <p role="status">{message}</p>

      {step === 1 && (
        <section>
          <h2>Personal information</h2>

          <p>
            Name: {data.first_name}{" "}
            {data.last_name}
          </p>

          <p>
            Phone: {data.phone_number ??
              "Not provided"}
          </p>

          <p>
            To change your name or phone number,
            use your agent profile settings.
          </p>

          <button onClick={() => setStep(2)}>
            Continue
          </button>
        </section>
      )}

      {step === 2 && (
        <form onSubmit={saveDetails}>
          <h2>Location and sales experience</h2>

          <label htmlFor="county">County</label>
          <input
            id="county"
            required
            minLength={2}
            maxLength={100}
            value={form.county ?? ""}
            onChange={(e) =>
              setForm({
                ...form,
                county: e.target.value,
              })
            }
          />

          <label htmlFor="city">City or town</label>
          <input
            id="city"
            required
            minLength={2}
            maxLength={100}
            value={form.city ?? ""}
            onChange={(e) =>
              setForm({
                ...form,
                city: e.target.value,
              })
            }
          />

          <label htmlFor="business">
            Business name (optional)
          </label>
          <input
            id="business"
            maxLength={150}
            value={form.business_name ?? ""}
            onChange={(e) =>
              setForm({
                ...form,
                business_name: e.target.value,
              })
            }
          />

          <label htmlFor="experience">
            Sales experience
          </label>
          <select
            id="experience"
            value={form.experience_level ?? ""}
            onChange={(e) =>
              setForm({
                ...form,
                experience_level:
                  e.target.value === ""
                    ? null
                    : e.target.value as
                        NonNullable<
                          OnboardingUpdate[
                            "experience_level"
                          ]
                        >,
              })
            }
          >
            <option value="">Select experience</option>
            <option value="beginner">
              Beginner
            </option>
            <option value="intermediate">
              Intermediate
            </option>
            <option value="experienced">
              Experienced
            </option>
          </select>

          <label htmlFor="category">
            Preferred sales category
          </label>
          <input
            id="category"
            maxLength={100}
            value={
              form.preferred_sales_category ?? ""
            }
            onChange={(e) =>
              setForm({
                ...form,
                preferred_sales_category:
                  e.target.value,
              })
            }
          />

          <div style={{ marginTop: 20 }}>
            <button
              type="button"
              onClick={() => setStep(1)}
            >
              Back
            </button>

            <button
              type="submit"
              disabled={saving}
            >
              {saving
                ? "Saving..."
                : "Save and continue"}
            </button>
          </div>
        </form>
      )}

      
{step === 3 && (
  <section>
    <h2>Prepare for KYC Verification</h2>

    <p>
      Your profile is{" "}
      <strong>
        {data.progress.percentage}% complete.
      </strong>
    </p>

    <p>
      Before proceeding with identity verification,
      ensure that your personal information is
      accurate and matches your identification
      document.
    </p>

    {/* Phase 6: KYC requirements from FastAPI */}
    <KycChecklist />

    <div
      style={{
        display: "flex",
        gap: "12px",
        marginTop: "24px",
        alignItems: "center",
      }}
    >
      <button
        type="button"
        onClick={() => setStep(2)}
        style={{
          padding: "10px 16px",
          borderRadius: "6px",
          cursor: "pointer",
        }}
      >
        Edit Details
      </button>

      <Link
        href="/dashboard"
        style={{
          display: "inline-block",
          padding: "10px 16px",
          backgroundColor: "#2563eb",
          color: "#ffffff",
          borderRadius: "6px",
          textDecoration: "none",
        }}
      >
        Return to Dashboard
      </Link>
    </div>
  </section>
)}

      </div>
    </main>
  );
}
