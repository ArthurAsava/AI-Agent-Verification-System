
import { createClient } from "@/lib/supabase/client";

import type {
  ReviewQueueResponse,
  ReviewerCase,
  VerificationDecisionRequest,
  VerificationDecisionResponse,
} from "./reviewer-types";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ReviewerApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ReviewerApiError";
  }
}

async function getAccessToken(): Promise<string> {
  const supabase = createClient();

  const {
    data: { session },
    error,
  } = await supabase.auth.getSession();

  if (error || !session?.access_token) {
    throw new ReviewerApiError(
      "Please sign in to continue.",
      401,
    );
  }

  return session.access_token;
}

async function reviewerRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getAccessToken();

  const response = await fetch(
    `${API_URL}/verification${path}`,
    {
      ...options,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.body
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
    },
  );

  if (!response.ok) {
    let message = "Reviewer request failed.";

    try {
      const body = await response.json();

      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Preserve the generic error message.
    }

    if (response.status === 403) {
      message = "You do not have reviewer permission.";
    }

    if (response.status === 409) {
      message =
        "This case has changed. Refresh before deciding.";
    }

    throw new ReviewerApiError(
      message,
      response.status,
    );
  }

  return (await response.json()) as T;
}

export function getReviewQueue(
  signal?: AbortSignal,
): Promise<ReviewQueueResponse> {
  return reviewerRequest<ReviewQueueResponse>(
    "/review-queue",
    { signal },
  );
}

export function getReviewerCase(
  caseId: string,
  signal?: AbortSignal,
): Promise<ReviewerCase> {
  return reviewerRequest<ReviewerCase>(
    `/cases/${encodeURIComponent(caseId)}`,
    { signal },
  );
}

export function submitReviewerDecision(
  caseId: string,
  payload: VerificationDecisionRequest,
): Promise<VerificationDecisionResponse> {
  return reviewerRequest<VerificationDecisionResponse>(
    `/cases/${encodeURIComponent(caseId)}/decision`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
