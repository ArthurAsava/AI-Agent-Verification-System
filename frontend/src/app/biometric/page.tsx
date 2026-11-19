"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AppHeader from "@/components/AppHeader";
import BiometricSelfieCapture from "@/components/BiometricSelfieCapture";
import { AgentApiError, getMyAgentProfile } from "@/lib/agent-api";
import { createClient } from "@/lib/supabase/client";

export default function BiometricPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;

    async function prepareBiometricCheck() {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();

      if (!active) return;
      if (!data.session) {
        router.replace("/login");
        return;
      }

      try {
        const profile = await getMyAgentProfile();
        if (!active) return;

        if (profile.status !== "under_review") {
          router.replace("/documents");
        }
      } catch (error) {
        if (!active) return;
        if (error instanceof AgentApiError && error.status === 404) {
          router.replace("/dashboard");
          return;
        }
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to prepare face verification.",
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    void prepareBiometricCheck();
    return () => {
      active = false;
    };
  }, [router]);

  return (
    <main className="app-page">
      <AppHeader />
      <div className="app-content workspace-stack">
        <header className="workspace-heading">
          <div>
            <p className="app-eyebrow">Step 3 of 3</p>
            <h1 className="app-title">Complete facial verification.</h1>
            <p className="app-subtitle">
              You will be securely redirected to the Didit sandbox to complete the provider-managed face-match and liveness check.
            </p>
          </div>
        </header>

        {loading ? (
          <p>Preparing the biometric sandbox...</p>
        ) : message ? (
          <section className="app-panel">
            <p role="alert">{message}</p>
            <Link className="button button--dark" href="/documents">
              Return to documents
            </Link>
          </section>
        ) : (
          <section className="app-panel">
            <BiometricSelfieCapture diditOnly />
          </section>
        )}
      </div>
    </main>
  );
}
