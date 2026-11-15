
"use client";

import Link from "next/link";
import useSWR from "swr";

import {
  getReviewQueue,
} from "@/lib/verification/reviewer-api";

export default function ReviewerDashboard() {
  const {
    data,
    error,
    isLoading,
    isValidating,
    mutate,
  } = useSWR(
    "reviewer-review-queue",
    () => getReviewQueue(),
    {
      revalidateOnFocus: false,
    },
  );

  const cases = data?.cases ?? [];

  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unable to load review queue."
        : null;

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">
              SalesMesh
            </p>

            <h1 className="mt-2 text-3xl font-bold">
              Verification Review Queue
            </h1>

            <p className="mt-2 text-slate-600">
              Review agent verification cases awaiting
              human decisions.
            </p>
          </div>

          <div className="flex gap-3">
            <Link
              href="/admin"
              className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-800"
            >
              Administration
            </Link>
            <Link
              href="/reviewer/biometrics"
              className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-800"
            >
              Biometric Queue
            </Link>
            <button
              type="button"
              onClick={() => void mutate()}
              disabled={isValidating}
              className="rounded-lg bg-slate-900 px-5 py-2.5 text-white disabled:opacity-50"
            >
              {isValidating
                ? "Refreshing..."
                : "Refresh Queue"}
            </button>
          </div>
        </header>

        {isLoading && (
          <p role="status">
            Loading review queue...
          </p>
        )}

        {errorMessage && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-700"
          >
            {errorMessage}
          </div>
        )}

        {!isLoading &&
          !errorMessage &&
          cases.length === 0 && (
            <div className="rounded-xl border bg-white p-8">
              No verification cases are awaiting review.
            </div>
          )}

        {!isLoading &&
          !errorMessage &&
          cases.length > 0 && (
            <div className="overflow-x-auto rounded-xl border bg-white">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-100">
                  <tr>
                    <th className="p-4">
                      Case
                    </th>

                    <th className="p-4">
                      Risk Level
                    </th>

                    <th className="p-4">
                      Risk Score
                    </th>

                    <th className="p-4">
                      Recommendation
                    </th>

                    <th className="p-4">
                      Action
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {cases.map((item) => (
                    <tr
                      key={item.id}
                      className="border-t"
                    >
                      <td className="p-4 font-mono text-xs">
                        {item.id.slice(0, 8)}...
                      </td>

                      <td className="p-4">
                        {item.risk_level ??
                          "Not available"}
                      </td>

                      <td className="p-4">
                        {item.risk_score ?? "N/A"}
                      </td>

                      <td className="p-4">
                        {item.recommendation ?? "N/A"}
                      </td>

                      <td className="p-4">
                        <Link
                          href={`/reviewer/cases/${item.id}`}
                          className="font-medium text-blue-700 hover:underline"
                        >
                          Review Case
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>
    </main>
  );
}
