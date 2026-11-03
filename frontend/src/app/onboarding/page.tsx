
"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import OnboardingProgress from
  "@/components/OnboardingProgress";

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
    return <main>Loading onboarding...</main>;
  }

  if (!data) {
    return (
      <main>
        <h1>Agent onboarding</h1>
        <p role="alert">{message}</p>
        <Link href="/dashboard">
          Return to dashboard
        </Link>
      </main>
    );
  }

  return (
    <main
      style={{
        maxWidth: 680,
        margin: "40px auto",
        padding: "20px",
      }}
    >
      <h1>SalesMesh Agent Onboarding</h1>

      <OnboardingProgress
        percentage={data.progress.percentage}
        completedFields={
          data.progress.completed_fields
        }
        totalFields={data.progress.total_fields}
      />

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
          <h2>Prepare for KYC verification</h2>

          <p>
            Your profile is{" "}
            {data.progress.percentage}% complete.
          </p>

          <p>
            Before identity verification, ensure
            your personal details are accurate.
          </p>

          <ul>
            <li>
              Have your valid identity document ready.
            </li>
            <li>
              Ensure your details match the document.
            </li>
            <li>
              Prepare for identity verification.
            </li>
          </ul>

          <p>
            Document uploads will become available
            in a later phase.
          </p>

          <button onClick={() => setStep(2)}>
            Edit details
          </button>

          <p>
            <Link href="/dashboard">
              Return to dashboard
            </Link>
          </p>
        </section>
      )}
    </main>
  );
}
