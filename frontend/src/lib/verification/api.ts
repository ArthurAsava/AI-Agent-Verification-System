
import type {
  AgentVerificationResponse,
} from "./types";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class VerificationApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "VerificationApiError";
  }
}

export async function getAgentVerification(
  accessToken: string,
  signal?: AbortSignal,
): Promise<AgentVerificationResponse> {
  let response: Response;

  try {
    response = await fetch(
      `${API_URL}/verification/me`,
      {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/json",
      },
      cache: "no-store",
      signal,
      },
    );
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }

    throw new VerificationApiError(
      "Verity could not reach its local API. Start the backend on port 8000, then refresh this page.",
      0,
    );
  }

  if (!response.ok) {
    if (response.status === 401) {
      throw new VerificationApiError(
        "Your session has expired. Please sign in again.",
        401,
      );
    }

    if (response.status === 404) {
      throw new VerificationApiError(
        "Complete your agent registration before checking verification.",
        404,
      );
    }

    throw new VerificationApiError(
      "Unable to load verification information.",
      response.status,
    );
  }

  return (await response.json()) as AgentVerificationResponse;
}
