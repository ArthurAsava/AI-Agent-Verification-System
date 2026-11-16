
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { createClient } from "@/lib/supabase/client";

import {
  getAgentVerification,
} from "@/lib/verification/api";
import {
  getDiditKycStatus,
  type DiditKycStatus,
} from "@/lib/kyc-api";

import {
  STATUS_INFORMATION,
  type VerificationCase,
} from "@/lib/verification/types";

import VerificationStatusBadge from "@/components/verification/VerificationStatusBadge";
import AppHeader from "@/components/AppHeader";

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString("en-KE", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function AgentVerificationPage() {
  const [cases, setCases] = useState<VerificationCase[]>([]);
  const [diditKycStatus, setDiditKycStatus] =
    useState<DiditKycStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadVerification = useCallback(
  async (signal?: AbortSignal) => {
    try {
      setError(null);

      const supabase = createClient();

      const {
        data: { session },
        error: sessionError,
      } = await supabase.auth.getSession();

        if (sessionError || !session?.access_token) {
          throw new Error(
            "Please sign in to view your verification status.",
          );
        }

        const [result, diditStatus] = await Promise.all([
          getAgentVerification(session.access_token, signal),
          getDiditKycStatus(),
        ]);

        if (!signal?.aborted) {
          setCases(result.cases);
          setDiditKycStatus(diditStatus);
        }
      } catch (err) {
        if (signal?.aborted) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load verification status.",
        );
      }
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();

    async function initialize() {
      setLoading(true);
      await loadVerification(controller.signal);

      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }

    void initialize();

    return () => controller.abort();
  }, [loadVerification]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await loadVerification();
    } finally {
      setRefreshing(false);
    }
  }

  const latestCase = cases[0];

  return (
    <main className="app-page">
      <AppHeader />
      <div className="app-content workspace-stack">
        <div className="workspace-heading">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">
              SalesMesh
            </p>

            <h1 className="mt-2 text-3xl font-bold">
              Agent Verification
            </h1>

            <p className="mt-2 text-sm text-slate-600">
              Track the progress of your identity verification.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={loading || refreshing}
            className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {refreshing ? "Refreshing..." : "Refresh Status"}
          </button>
        </div>

        {loading ? (
          <div className="rounded-xl border bg-white p-8 text-slate-600">
            Loading your verification information...
          </div>
        ) : error ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-700"
          >
            {error}
          </div>
        ) : (
          <>
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold">
                Current Verification Status
              </h2>

              {!latestCase ? (
                <div className="mt-5 space-y-3">
                  <p className="text-slate-600">
                    You do not have any verification cases yet.
                  </p>

                  <Link
                    href="/dashboard"
                    className="inline-block text-sm font-medium text-blue-700 hover:underline"
                  >
                    Return to Dashboard
                  </Link>
                </div>
              ) : (
                <div className="mt-5 space-y-4">
                  <VerificationStatusBadge
                    status={latestCase.status}
                  />

                  <p className="text-slate-600">
                    {
                      STATUS_INFORMATION[latestCase.status]
                        .description
                    }
                  </p>

                  <div className="grid gap-4 border-t pt-5 sm:grid-cols-2">
                    <div>
                      <p className="text-xs uppercase text-slate-500">
                        Case Reference
                      </p>
                      <p className="mt-1 break-all text-sm font-medium">
                        {latestCase.id}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs uppercase text-slate-500">
                        Last Updated
                      </p>
                      <p className="mt-1 text-sm font-medium">
                        {formatDate(latestCase.updated_at)}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold">
                Hosted KYC Verification
              </h2>

              {!diditKycStatus ? (
                <p className="mt-3 text-sm text-slate-600">
                  No hosted KYC verification has been started yet.
                </p>
              ) : (
                <div className="mt-4 space-y-3 text-sm">
                  <p className="text-slate-700">
                    Provider result: {diditKycStatus.provider_status ?? "Awaiting provider update"}
                    {diditKycStatus.is_final === true
                      ? " (final provider update)"
                      : ""}
                  </p>
                  <p className="text-slate-600">
                    SalesMesh review state: {diditKycStatus.check_status.replaceAll("_", " ")}. A provider result does not automatically approve your account.
                  </p>
                  {Object.keys(diditKycStatus.actions).length > 0 && (
                    <ul className="list-disc space-y-1 pl-5 text-slate-600">
                      {Object.entries(diditKycStatus.actions).map(([name, value]) => (
                        <li key={name}>
                          {name.replaceAll("_", " ")}: {value}
                        </li>
                      ))}
                    </ul>
                  )}
                  {diditKycStatus.synced_at && (
                    <p className="text-xs text-slate-500">
                      Last synchronized: {formatDate(diditKycStatus.synced_at)}
                    </p>
                  )}
                </div>
              )}
            </section>

            <section className="space-y-4">
              <h2 className="text-xl font-semibold">
                Verification History
              </h2>

              {cases.length === 0 ? (
                <div className="rounded-xl border bg-white p-6 text-slate-600">
                  No verification history is available.
                </div>
              ) : (
                <div className="space-y-3">
                  {cases.map((item) => (
                    <article
                      key={item.id}
                      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold">
                            Verification Case
                          </p>
                          <p className="mt-1 break-all text-xs text-slate-500">
                            {item.id}
                          </p>
                        </div>

                        <VerificationStatusBadge
                          status={item.status}
                        />
                      </div>

                      <p className="mt-4 text-sm text-slate-600">
                        {
                          STATUS_INFORMATION[item.status]
                            .description
                        }
                      </p>

                      <p className="mt-3 text-xs text-slate-500">
                        Submitted: {formatDate(item.created_at)}
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
