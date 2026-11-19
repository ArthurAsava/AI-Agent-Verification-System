"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AppHeader from "@/components/AppHeader";
import KycDocumentManager from "@/components/KycDocumentManager";
import {
  AgentApiError,
  getMyAgentProfile,
} from "@/lib/agent-api";
import { createClient } from "@/lib/supabase/client";

export default function DocumentsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [documentSubmitted, setDocumentSubmitted] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;

    async function prepareDocuments() {
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

        const profileComplete = Boolean(
          profile.date_of_birth &&
          profile.primary_residence &&
          profile.nationality &&
          profile.avatar_variant,
        );

        if (!profileComplete) {
          router.replace("/dashboard");
          return;
        }

        setDocumentSubmitted(profile.status === "under_review");
      } catch (error) {
        if (!active) return;
        if (error instanceof AgentApiError && error.status === 404) {
          router.replace("/dashboard");
          return;
        }
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to prepare document verification.",
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    void prepareDocuments();
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
            <p className="app-eyebrow">Step 2 of 3</p>
            <h1 className="app-title">Submit your identity document.</h1>
            <p className="app-subtitle">
              Upload a clear National ID front or passport, then submit it for review before continuing to the facial verification sandbox.
            </p>
          </div>
        </header>

        {loading ? (
          <p>Loading your secure document workspace...</p>
        ) : message ? (
          <section className="app-panel">
            <p role="alert">{message}</p>
            <Link className="button button--dark" href="/dashboard">
              Return to dashboard
            </Link>
          </section>
        ) : (
          <section className="app-panel">
            <KycDocumentManager
              onVerificationSubmitted={() => setDocumentSubmitted(true)}
            />

            {documentSubmitted && (
              <div className="app-panel__action">
                <h2>Your document has been submitted.</h2>
                <p>
                  Continue to Didit&apos;s sandbox for the final document, face-match, and liveness step.
                </p>
                <Link className="button button--gold" href="/biometric">
                  Continue to face verification <span aria-hidden="true">→</span>
                </Link>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
