
"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";

import {
  getReviewerCase,
  submitReviewerDecision,
} from "@/lib/verification/reviewer-api";

import type {
  ReviewerAction,
} from "@/lib/verification/reviewer-types";

interface Props {
  caseId: string;
}

export default function ReviewerCaseClient({
  caseId,
}: Props) {
  const [action, setAction] =
    useState<ReviewerAction>("approve");

  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [decisionError, setDecisionError] =
    useState<string | null>(null);
  const [success, setSuccess] =
    useState<string | null>(null);

  const {
    data: reviewCase,
    error: fetchError,
    isLoading,
    isValidating,
    mutate,
  } = useSWR(
    ["reviewer-case", caseId],
    ([, id]: [string, string]) => getReviewerCase(id),
    {
      revalidateOnFocus: false,
    },
  );

  async function handleDecision(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!reviewCase || submitting) return;

    const normalizedReason = reason.trim();

    if (
      normalizedReason.length < 10 ||
      normalizedReason.length > 1000
    ) {
      setDecisionError(
        "Provide a reason containing 10 to 1000 characters.",
      );
      return;
    }

    const confirmed = window.confirm(
      `Confirm ${action.replaceAll("_", " ")} for this case?`,
    );

    if (!confirmed) return;

    setSubmitting(true);
    setDecisionError(null);
    setSuccess(null);

    try {
      const result = await submitReviewerDecision(
        reviewCase.id,
        {
          action,
          reason: normalizedReason,
          expected_version: reviewCase.version,
        },
      );

      setSuccess(
        `Decision saved. New status: ${result.new_status}`,
      );

      setReason("");

      await mutate();
    } catch (err) {
      setDecisionError(
        err instanceof Error
          ? err.message
          : "Could not save decision.",
      );

      // Refresh the case after a conflict or failed decision.
      // Keep the decision error visible to the reviewer.
      try {
        await mutate();
      } catch {
        // The existing error remains visible.
      }
    } finally {
      setSubmitting(false);
    }
  }

  const errorMessage =
    fetchError instanceof Error
      ? fetchError.message
      : fetchError
        ? "Unable to load verification case."
        : null;

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10 text-slate-900">
      <div className="mx-auto max-w-4xl space-y-6">
        <Link
          href="/reviewer"
          className="text-sm font-medium text-blue-700 hover:underline"
        >
          Back to Review Queue
        </Link>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-3xl font-bold">
            Verification Case Details
          </h1>

          <button
            type="button"
            onClick={() => {
              setDecisionError(null);
              void mutate();
            }}
            disabled={isValidating || submitting}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {isValidating
              ? "Refreshing..."
              : "Refresh Case"}
          </button>
        </div>

        {isLoading && (
          <p role="status">
            Loading verification case...
          </p>
        )}

        {errorMessage && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700"
          >
            {errorMessage}
          </div>
        )}

        {decisionError && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700"
          >
            {decisionError}
          </div>
        )}

        {success && (
          <div
            role="status"
            className="rounded-lg border border-green-200 bg-green-50 p-4 text-green-800"
          >
            {success}
          </div>
        )}

        {!isLoading && !errorMessage && reviewCase && (
          <>
            <section className="rounded-xl border bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">
                Case Information
              </h2>

              <dl className="mt-5 grid gap-5 sm:grid-cols-2">
                {[
                  ["Case ID", reviewCase.id],
                  ["Agent ID", reviewCase.agent_id],
                  ["Document ID", reviewCase.document_id],
                  ["Status", reviewCase.status],
                  [
                    "Recommendation",
                    reviewCase.recommendation ?? "N/A",
                  ],
                  [
                    "Risk Level",
                    reviewCase.risk_level ?? "N/A",
                  ],
                  [
                    "Risk Score",
                    reviewCase.risk_score?.toString() ?? "N/A",
                  ],
                  [
                    "Scoring Version",
                    reviewCase.scoring_version ?? "N/A",
                  ],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs font-medium uppercase text-slate-500">
                      {label}
                    </dt>

                    <dd className="mt-1 break-all text-sm font-medium">
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>

            {reviewCase.decision_reason && (
              <section className="rounded-xl border bg-white p-6">
                <h2 className="font-semibold">
                  Previous Decision
                </h2>

                <p className="mt-3 whitespace-pre-wrap text-sm">
                  {reviewCase.decision_reason}
                </p>
              </section>
            )}

            {reviewCase.fraud_assessment && (
              <section className="rounded-xl border border-amber-200 bg-amber-50 p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-amber-950">
                      Fraud-Signal Assessment
                    </h2>
                    <p className="mt-1 text-sm text-amber-900">
                      {reviewCase.fraud_assessment.model_version} · risk score {reviewCase.fraud_assessment.risk_score} · {reviewCase.fraud_assessment.risk_level}
                    </p>
                  </div>
                  <span className="rounded-full bg-amber-200 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-amber-950">
                    Human review required
                  </span>
                </div>

                {reviewCase.fraud_assessment.signals.length === 0 ? (
                  <p className="mt-4 text-sm text-amber-900">
                    No fraud signals were recorded for this assessment.
                  </p>
                ) : (
                  <ul className="mt-5 space-y-3">
                    {reviewCase.fraud_assessment.signals.map((signal) => (
                      <li
                        key={signal.code}
                        className="rounded-lg border border-amber-200 bg-white p-4"
                      >
                        <p className="font-semibold text-slate-900">
                          {signal.code.replaceAll("_", " ")}
                        </p>
                        <p className="mt-1 text-sm text-slate-700">
                          {signal.description}
                        </p>
                        {Object.keys(signal.evidence).length > 0 && (
                          <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-600">
                            {Object.entries(signal.evidence).map(([key, value]) => (
                              <div key={key}>
                                <dt className="inline font-medium capitalize">
                                  {key.replaceAll("_", " ")}:
                                </dt>{" "}
                                <dd className="inline">{String(value)}</dd>
                              </div>
                            ))}
                          </dl>
                        )}
                      </li>
                    ))}
                  </ul>
                )}

                <p className="mt-5 text-xs text-amber-950">
                  These signals are review evidence, not proof of fraud or an automated decision.
                </p>
              </section>
            )}

            {reviewCase.status === "awaiting_review" && (
              <form
                onSubmit={(event) =>
                  void handleDecision(event)
                }
                className="space-y-5 rounded-xl border bg-white p-6 shadow-sm"
              >
                <h2 className="text-xl font-semibold">
                  Record Human Decision
                </h2>

                <div>
                  <label
                    htmlFor="review-action"
                    className="mb-2 block text-sm font-medium"
                  >
                    Decision
                  </label>

                  <select
                    id="review-action"
                    value={action}
                    onChange={(event) =>
                      setAction(
                        event.target.value as ReviewerAction,
                      )
                    }
                    disabled={submitting}
                    className="w-full rounded-lg border p-3"
                  >
                    <option value="approve">
                      Approve
                    </option>

                    <option value="reject">
                      Reject
                    </option>

                    <option value="request_resubmission">
                      Request Resubmission
                    </option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="review-reason"
                    className="mb-2 block text-sm font-medium"
                  >
                    Decision Reason
                  </label>

                  <textarea
                    id="review-reason"
                    value={reason}
                    onChange={(event) =>
                      setReason(event.target.value)
                    }
                    minLength={10}
                    maxLength={1000}
                    required
                    disabled={submitting}
                    rows={5}
                    className="w-full rounded-lg border p-3"
                    placeholder="Explain the evidence and reason for your decision..."
                  />

                  <p className="mt-1 text-xs text-slate-500">
                    {reason.trim().length}/1000 characters
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={
                    submitting ||
                    isValidating ||
                    reason.trim().length < 10 ||
                    reason.trim().length > 1000
                  }
                  className="rounded-lg bg-slate-900 px-6 py-3 font-medium text-white disabled:opacity-50"
                >
                  {submitting
                    ? "Saving Decision..."
                    : "Submit Decision"}
                </button>
              </form>
            )}

            {reviewCase.status !== "awaiting_review" && (
              <p className="rounded-xl border bg-white p-5 text-slate-600">
                This case is not currently eligible for
                a reviewer decision.
              </p>
            )}
          </>
        )}
      </div>
    </main>
  );
}
