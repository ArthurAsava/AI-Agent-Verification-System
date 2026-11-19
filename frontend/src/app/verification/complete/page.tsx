"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AppHeader from "@/components/AppHeader";

export default function VerificationCompletePage() {
  const router = useRouter();

  useEffect(() => {
    const redirect = window.setTimeout(() => {
      router.replace("/?verification=submitted");
    }, 1800);

    return () => window.clearTimeout(redirect);
  }, [router]);

  return (
    <main className="app-page">
      <AppHeader />
      <div className="app-content">
        <section className="app-panel">
          <p className="app-eyebrow">Verification submitted</p>
          <h1 className="app-title">Your profile is now being reviewed.</h1>
          <p className="app-subtitle">
            We have received your submission and will return you to the Verity home page momentarily.
          </p>
          <Link className="button button--gold" href="/">
            Return home now <span aria-hidden="true">→</span>
          </Link>
        </section>
      </div>
    </main>
  );
}
