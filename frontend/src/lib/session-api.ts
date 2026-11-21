import { createClient } from "@/lib/supabase/client";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export type AccountSession = {
  id: string;
  created_at: string | null;
  last_active_at: string | null;
  expires_at: string | null;
  user_agent: string | null;
  is_current: boolean;
};

export class SessionApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export type AccountDeletionEligibility = {
  eligible: boolean;
};

async function getAccessToken() {
  const supabase = createClient();
  const { data, error } = await supabase.auth.getSession();

  if (error || !data.session) {
    throw new SessionApiError("Please sign in first.", 401);
  }

  return data.session.access_token;
}

async function accountRequest(path: string, init?: RequestInit) {
  const accessToken = await getAccessToken();
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);

  try {
    return await fetch(`${API_URL}/api/v1/auth${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new SessionApiError(
      "Verity could not reach the local API. Check that it is running, then try again.",
      0,
    );
  }
}

/** Returns only the signed-in user's session records. */
export async function getMyAccountSessions(): Promise<AccountSession[]> {
  const response = await accountRequest("/sessions");

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new SessionApiError(
      body.detail ?? `Request failed: ${response.status}`,
      response.status,
    );
  }

  return (await response.json()) as AccountSession[];
}

export async function getAccountDeletionEligibility(): Promise<AccountDeletionEligibility> {
  const response = await accountRequest("/account-deletion-eligibility");

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new SessionApiError(
      body.detail ?? `Request failed: ${response.status}`,
      response.status,
    );
  }

  return (await response.json()) as AccountDeletionEligibility;
}

export async function deleteMyAccount(password: string): Promise<void> {
  const response = await accountRequest("/delete-account", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new SessionApiError(
      body.detail ?? `Request failed: ${response.status}`,
      response.status,
    );
  }
}
