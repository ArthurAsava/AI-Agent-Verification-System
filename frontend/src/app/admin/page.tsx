"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import useSWR from "swr";

import {
  getAdminDashboardSummary,
  getReviewerAccess,
  updateReviewerAccess,
} from "@/lib/verification/reviewer-api";
import type {
  ReviewerAccessEntry,
} from "@/lib/verification/reviewer-types";


const SUMMARY_CARDS = [
  {
    key: "awaiting_review_cases",
    label: "Awaiting review",
    description: "Document cases requiring a human decision",
  },
  {
    key: "elevated_risk_cases",
    label: "Elevated risk",
    description: "Open cases scored high or critical",
  },
  {
    key: "new_cases_last_24_hours",
    label: "New in 24 hours",
    description: "Recently submitted verification cases",
  },
  {
    key: "agents_under_review",
    label: "Agents under review",
    description: "Agents without a completed staff decision",
  },
  {
    key: "active_reviewers",
    label: "Active reviewers",
    description: "Staff with active workflow access",
  },
] as const;


function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}


export default function AdministratorDashboard() {
  const summaryQuery = useSWR(
    "administrator-dashboard-summary",
    () => getAdminDashboardSummary(),
    { revalidateOnFocus: false },
  );
  const reviewersQuery = useSWR(
    "administrator-reviewer-access",
    () => getReviewerAccess(),
    { revalidateOnFocus: false },
  );
  const [targetUserId, setTargetUserId] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [savingUserId, setSavingUserId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loading = summaryQuery.isLoading || reviewersQuery.isLoading;
  const fetchError = summaryQuery.error ?? reviewersQuery.error;
  const summary = summaryQuery.data;
  const reviewers = reviewersQuery.data?.reviewers ?? [];

  async function saveReviewer(
    userId: string,
    active: boolean,
    admin: boolean,
  ): Promise<boolean> {
    setSavingUserId(userId);
    setActionError(null);
    setSuccess(null);

    try {
      await updateReviewerAccess(userId, {
        is_active: active,
        is_admin: admin,
      });
      await reviewersQuery.mutate();
      await summaryQuery.mutate();
      setSuccess("Reviewer access was updated.");
      return true;
    } catch (error) {
      setActionError(errorMessage(error, "Could not update reviewer access."));
      return false;
    } finally {
      setSavingUserId(null);
    }
  }

  function submitNewReviewer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedUserId = targetUserId.trim();

    if (!normalizedUserId) {
      setActionError("Enter the existing SalesMesh user UUID.");
      return;
    }

    void saveReviewer(normalizedUserId, isActive, isAdmin).then((saved) => {
      if (saved) {
        setTargetUserId("");
      }
    });
  }

  function roleLabel(reviewer: ReviewerAccessEntry) {
    if (reviewer.is_admin) return "Administrator";
    return "Reviewer";
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-8">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">
              SalesMesh
            </p>
            <h1 className="mt-2 text-3xl font-bold">
              Verification Administration
            </h1>
            <p className="mt-2 max-w-3xl text-slate-600">
              Monitor the human-review workflow and manage staff access. Dashboard metrics contain no identity or biometric data.
            </p>
          </div>
          <div className="flex gap-3">
            <Link
              href="/reviewer"
              className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-800"
            >
              Review Queue
            </Link>
            <button
              type="button"
              onClick={() => {
                setActionError(null);
                void Promise.all([
                  summaryQuery.mutate(),
                  reviewersQuery.mutate(),
                ]);
              }}
              disabled={summaryQuery.isValidating || reviewersQuery.isValidating}
              className="rounded-lg bg-slate-900 px-5 py-2.5 font-medium text-white disabled:opacity-50"
            >
              Refresh
            </button>
          </div>
        </header>

        {loading && <p role="status">Loading administration dashboard...</p>}

        {fetchError && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-700"
          >
            {errorMessage(fetchError, "Unable to load administrator data.")}
          </div>
        )}

        {actionError && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-700"
          >
            {actionError}
          </div>
        )}

        {success && (
          <div
            role="status"
            className="rounded-xl border border-green-200 bg-green-50 p-5 text-green-800"
          >
            {success}
          </div>
        )}

        {summary && (
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {SUMMARY_CARDS.map((card) => (
              <article key={card.key} className="rounded-xl border bg-white p-5 shadow-sm">
                <p className="text-sm font-medium text-slate-600">{card.label}</p>
                <p className="mt-2 text-3xl font-bold">
                  {summary[card.key]}
                </p>
                <p className="mt-2 text-sm text-slate-500">{card.description}</p>
              </article>
            ))}
          </section>
        )}

        {!loading && !fetchError && (
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(330px,0.8fr)]">
            <div className="overflow-x-auto rounded-xl border bg-white shadow-sm">
              <div className="border-b p-5">
                <h2 className="text-xl font-semibold">Reviewer access</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Only existing SalesMesh accounts can receive reviewer or administrator access.
                </p>
              </div>
              {reviewers.length === 0 ? (
                <p className="p-5 text-sm text-slate-600">No reviewer accounts are configured.</p>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-100 text-slate-700">
                    <tr>
                      <th className="p-4">User</th>
                      <th className="p-4">Role</th>
                      <th className="p-4">Status</th>
                      <th className="p-4">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reviewers.map((reviewer) => {
                      const saving = savingUserId === reviewer.user_id;
                      return (
                        <tr key={reviewer.user_id} className="border-t">
                          <td className="p-4 font-mono text-xs">{reviewer.user_id}</td>
                          <td className="p-4">{roleLabel(reviewer)}</td>
                          <td className="p-4">{reviewer.is_active ? "Active" : "Inactive"}</td>
                          <td className="p-4">
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                disabled={saving}
                                onClick={() => void saveReviewer(
                                  reviewer.user_id,
                                  !reviewer.is_active,
                                  reviewer.is_admin,
                                )}
                                className="rounded border border-slate-300 px-3 py-1.5 font-medium disabled:opacity-50"
                              >
                                {reviewer.is_active ? "Deactivate" : "Activate"}
                              </button>
                              <button
                                type="button"
                                disabled={saving}
                                onClick={() => void saveReviewer(
                                  reviewer.user_id,
                                  reviewer.is_active,
                                  !reviewer.is_admin,
                                )}
                                className="rounded border border-slate-300 px-3 py-1.5 font-medium disabled:opacity-50"
                              >
                                {reviewer.is_admin ? "Revoke admin" : "Grant admin"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            <form onSubmit={submitNewReviewer} className="h-fit rounded-xl border bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Add or update staff access</h2>
              <p className="mt-2 text-sm text-slate-600">
                Use the UUID of an existing SalesMesh account. Emails are never listed in this screen.
              </p>
              <label className="mt-5 block text-sm font-medium">
                User UUID
                <input
                  value={targetUserId}
                  onChange={(event) => setTargetUserId(event.target.value)}
                  required
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="mt-1 block w-full rounded-lg border border-slate-300 p-3 font-mono text-sm"
                />
              </label>
              <label className="mt-4 flex items-center gap-3 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(event) => setIsActive(event.target.checked)}
                />
                Active reviewer access
              </label>
              <label className="mt-3 flex items-center gap-3 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={isAdmin}
                  onChange={(event) => setIsAdmin(event.target.checked)}
                />
                Administrator access
              </label>
              <button
                type="submit"
                disabled={savingUserId !== null}
                className="mt-6 rounded-lg bg-slate-900 px-5 py-2.5 font-medium text-white disabled:opacity-50"
              >
                {savingUserId ? "Saving..." : "Save access"}
              </button>
            </form>
          </section>
        )}

        <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          Reviewer and administrator roles provide workflow access only. Fraud scores and provider outcomes remain human-review evidence; they never make an automated access decision.
        </p>
      </div>
    </main>
  );
}
