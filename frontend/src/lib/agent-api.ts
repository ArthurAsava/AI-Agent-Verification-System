
import { createClient } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export interface AgentProfile {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  phone_number: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AgentRegistration {
  first_name: string;
  last_name: string;
  phone_number?: string | null;
}

async function authorizedRequest(
  path: string,
  options: RequestInit = {}
) {
  const supabase = createClient();

  const { data, error } =
    await supabase.auth.getSession();

  if (error || !data.session) {
    throw new Error("Please sign in first");
  }

  const response = await fetch(
    `${API_URL}${path}`,
    {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
        Authorization:
          `Bearer ${data.session.access_token}`,
      },
      cache: "no-store",
    }
  );

  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({}));

    throw new Error(
      body.detail ??
      `Request failed: ${response.status}`
    );
  }

  return response.json();
}

export async function registerAgent(
  payload: AgentRegistration
): Promise<AgentProfile> {
  return authorizedRequest(
    "/api/v1/agents/register",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function getMyAgentProfile():
  Promise<AgentProfile> {
  return authorizedRequest("/api/v1/agents/me");
}
