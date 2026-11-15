"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";

import {
  downloadBiometricReviewDocument,
  getBiometricReviewQueue,
  submitBiometricReviewDecision,
} from "@/lib/verification/reviewer-api";
import type {
  BiometricReviewerAction,
  ReviewerDocumentSummary,
} from "@/lib/verification/reviewer-types";

interface Preview {
  documentId: string;
  documentType: string;
  mimeType: string;
  objectUrl: string;
}

const ACTION_LABELS: Record<BiometricReviewerAction, string> = {
  confirm_match: "Confirm manual comparison",
  request_resubmission: "Request a new selfie or document",
  reject_capture: "Reject this capture",
};

function documentLabel(document: ReviewerDocumentSummary) {
  return document.document_type.replaceAll("_", " ");
}

function formatFileSize(size: number | null) {
  if (!size) {
    return "Size unavailable";
  }

  return `${Math.ceil(size / 1024)} KB`;
}

export default function BiometricReviewPage() {
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    "reviewer-biometric-review-queue",
    () => getBiometricReviewQueue(),
    { revalidateOnFocus: false },
  );
  const [preview, setPreview] = useState<Preview | null>(null);
  const [actions, setActions] = useState<
    Record<string, BiometricReviewerAction>
  >({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [submittingCheckId, setSubmittingCheckId] = useState<string | null>(
    null,
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const previewUrlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  const items = data?.items ?? [];
  const errorMessage =
    error instanceof Error
      ? error.message
      : error
        ? "Unable to load biometric review queue."
        : null;

  async function openPreview(
    checkId: string,
    document: ReviewerDocumentSummary,
  ) {
    setActionError(null);

    try {
      const downloaded = await downloadBiometricReviewDocument(
        checkId,
        document.document_id,
      );
      const objectUrl = URL.createObjectURL(downloaded.blob);

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
      previewUrlRef.current = objectUrl;
      setPreview({
        documentId: document.document_id,
        documentType: documentLabel(document),
        mimeType: downloaded.mimeType,
        objectUrl,
      });
    } catch (previewError) {
      setActionError(
        previewError instanceof Error
          ? previewError.message
          : "Unable to open the review document.",
      );
    }
  }

  async function submitDecision(checkId: string) {
    const action = actions[checkId] ?? "confirm_match";
    const reason = reasons[checkId]?.trim() ?? "";

    if (reason.length < 10) {
      setActionError("Enter a decision reason of at least 10 characters.");
      return;
    }

    setActionError(null);
    setSubmittingCheckId(checkId);
    try {
      await submitBiometricReviewDecision(checkId, { action, reason });
      setPreview((currentPreview) => {
        if (currentPreview && previewUrlRef.current) {
          URL.revokeObjectURL(previewUrlRef.current);
          previewUrlRef.current = null;
        }
        return null;
      });
      setReasons((current) => {
        const next = { ...current };
        delete next[checkId];
        return next;
      });
      await mutate();
    } catch (decisionError) {
      setActionError(
        decisionError instanceof Error
          ? decisionError.message
          : "Unable to save biometric review decision.",
      );
    } finally {
      setSubmittingCheckId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">
              SalesMesh
            </p>
            <h1 className="mt-2 text-3xl font-bold">
              Biometric Evidence Review
            </h1>
            <p className="mt-2 max-w-3xl text-slate-600">
              Compare a consented selfie with available identity evidence.
              This is a human evidence review only: it does not perform
              liveness detection, automated face matching, or agent approval.
            </p>
          </div>

          <div className="flex gap-3">
            <Link
              href="/reviewer"
              className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 font-medium text-slate-800"
            >
              Document Queue
            </Link>
            <button
              type="button"
              onClick={() => void mutate()}
              disabled={isValidating}
              className="rounded-lg bg-slate-900 px-5 py-2.5 text-white disabled:opacity-50"
            >
              {isValidating ? "Refreshing..." : "Refresh Queue"}
            </button>
          </div>
        </header>

        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Sensitive documents are fetched through the authenticated backend,
          displayed only for this session, and never exposed through a public
          Storage link.
        </div>

        {actionError && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700"
          >
            {actionError}
          </div>
        )}

        {isLoading && <p role="status">Loading biometric review queue...</p>}

        {errorMessage && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-700"
          >
            {errorMessage}
          </div>
        )}

        {!isLoading && !errorMessage && items.length === 0 && (
          <div className="rounded-xl border bg-white p-8">
            No biometric evidence is awaiting human review.
          </div>
        )}

        {!isLoading && !errorMessage && items.length > 0 && (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
            <section className="space-y-5">
              {items.map((item) => {
                const selectedAction = actions[item.check_id] ?? "confirm_match";
                const isSubmitting = submittingCheckId === item.check_id;
                const selfie = item.selfie;

                return (
                  <article
                    key={item.check_id}
                    className="rounded-xl border bg-white p-6 shadow-sm"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h2 className="font-semibold">Biometric evidence review</h2>
                        <p className="mt-1 font-mono text-xs text-slate-500">
                          Review {item.check_id.slice(0, 8)}...
                        </p>
                      </div>
                      <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
                        Awaiting review
                      </span>
                    </div>

                    <div className="mt-5 grid gap-4 sm:grid-cols-2">
                      {selfie ? (
                        <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
                          <p className="text-sm font-semibold capitalize">
                            Consented selfie
                          </p>
                          <p className="mt-1 text-xs text-slate-600">
                            {selfie.mime_type ?? "Unknown format"} · {formatFileSize(selfie.file_size_bytes)}
                          </p>
                          <button
                            type="button"
                            onClick={() => void openPreview(item.check_id, selfie)}
                            className="mt-3 font-medium text-blue-700 hover:underline"
                          >
                            Open selfie
                          </button>
                        </div>
                      ) : (
                        <div className="rounded-lg border border-violet-100 bg-violet-50 p-4">
                          <p className="text-sm font-semibold">Hosted provider capture</p>
                          <p className="mt-1 text-xs text-slate-600">
                            Didit captured biometric evidence in its hosted flow; SalesMesh retains only the limited provider summary below.
                          </p>
                        </div>
                      )}

                      <div className="rounded-lg border p-4">
                        <p className="text-sm font-semibold">Identity evidence</p>
                        {item.identity_documents.length === 0 ? (
                          <p className="mt-1 text-sm text-slate-600">
                            No compatible identity document is available.
                          </p>
                        ) : (
                          <ul className="mt-2 space-y-2 text-sm">
                            {item.identity_documents.map((document) => (
                              <li key={document.document_id}>
                                <button
                                  type="button"
                                  onClick={() => void openPreview(item.check_id, document)}
                                  className="font-medium capitalize text-blue-700 hover:underline"
                                >
                                  Open {documentLabel(document)}
                                </button>
                                <span className="text-slate-500">
                                  {" "}· {document.mime_type ?? "Unknown format"}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>

                    {item.provider_summary && (
                      <div className="mt-4 rounded-lg border border-violet-100 bg-violet-50 p-4 text-sm">
                        <p className="font-semibold text-violet-950">
                          Didit provider evidence
                        </p>
                        <p className="mt-1 text-violet-900">
                          {item.provider_summary.mode.replaceAll("_", " ")} · {item.provider_summary.submission_status}
                          {item.provider_summary.is_final === true
                            ? " · final provider update"
                            : ""}
                        </p>
                        {item.provider_summary.result_text && (
                          <p className="mt-2 text-violet-900">
                            {item.provider_summary.result_text}
                          </p>
                        )}
                        {Object.keys(item.provider_summary.actions).length > 0 && (
                          <ul className="mt-2 list-disc pl-5 text-violet-900">
                            {Object.entries(item.provider_summary.actions).map(([name, value]) => (
                              <li key={name}>
                                {name.replaceAll("_", " ")}: {value}
                              </li>
                            ))}
                          </ul>
                        )}
                        <p className="mt-2 text-xs text-violet-800">
                          Provider output is evidence only; your recorded human decision controls the SalesMesh outcome.
                        </p>
                      </div>
                    )}

                    <div className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                      <label className="text-sm font-medium">
                        Decision
                        <select
                          value={selectedAction}
                          onChange={(event) =>
                            setActions((current) => ({
                              ...current,
                              [item.check_id]: event.target.value as BiometricReviewerAction,
                            }))
                          }
                          className="mt-1 block w-full rounded-lg border border-slate-300 bg-white p-2"
                        >
                          {Object.entries(ACTION_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <button
                        type="button"
                        onClick={() => void submitDecision(item.check_id)}
                        disabled={isSubmitting}
                        className="self-end rounded-lg bg-slate-900 px-5 py-2.5 text-white disabled:opacity-50"
                      >
                        {isSubmitting ? "Saving..." : "Save review"}
                      </button>
                    </div>

                    <label className="mt-3 block text-sm font-medium">
                      Required review reason
                      <textarea
                        value={reasons[item.check_id] ?? ""}
                        onChange={(event) =>
                          setReasons((current) => ({
                            ...current,
                            [item.check_id]: event.target.value,
                          }))
                        }
                        minLength={10}
                        maxLength={1000}
                        rows={3}
                        placeholder="Record the basis for this human evidence decision."
                        className="mt-1 block w-full rounded-lg border border-slate-300 p-2"
                      />
                    </label>
                  </article>
                );
              })}
            </section>

            <aside className="h-fit rounded-xl border bg-white p-5 shadow-sm">
              <h2 className="font-semibold">Secure document preview</h2>
              {!preview && (
                <p className="mt-2 text-sm text-slate-600">
                  Open a selfie or identity document to inspect it here.
                </p>
              )}
              {preview && (
                <div className="mt-4 space-y-3">
                  <p className="text-sm capitalize text-slate-600">
                    {preview.documentType}
                  </p>
                  {preview.mimeType.startsWith("image/") ? (
                    // Blob URLs are intentionally never sent to a remote image optimizer.
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={preview.objectUrl}
                      alt="Sensitive identity evidence preview"
                      className="max-h-[600px] w-full rounded-lg border object-contain"
                    />
                  ) : (
                    <iframe
                      title="Sensitive identity evidence preview"
                      src={preview.objectUrl}
                      className="h-[600px] w-full rounded-lg border"
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      if (previewUrlRef.current) {
                        URL.revokeObjectURL(previewUrlRef.current);
                        previewUrlRef.current = null;
                      }
                      setPreview(null);
                    }}
                    className="text-sm font-medium text-blue-700 hover:underline"
                  >
                    Close preview
                  </button>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>
    </main>
  );
}
