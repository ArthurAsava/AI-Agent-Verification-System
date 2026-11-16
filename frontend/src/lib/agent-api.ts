
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
  avatar_variant: "male" | "female" | null;
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


export interface OnboardingProgress {
  completed_fields: number;
  total_fields: number;
  percentage: number;
  missing_fields: string[];
  profile_complete: boolean;
}

export interface OnboardingData {
  agent_id: string;
  first_name: string;
  last_name: string;
  phone_number: string | null;
  county: string | null;
  city: string | null;
  business_name: string | null;
  experience_level: string | null;
  preferred_sales_category: string | null;
  agent_status: string;
  progress: OnboardingProgress;
}

export interface OnboardingUpdate {
  county?: string | null;
  city?: string | null;
  business_name?: string | null;
  experience_level?:
    | "beginner"
    | "intermediate"
    | "experienced"
    | null;
  preferred_sales_category?: string | null;
}

export async function getMyOnboarding():
  Promise<OnboardingData> {
  return authorizedRequest(
    "/api/v1/onboarding/me"
  );
}

export async function updateMyOnboarding(
  payload: OnboardingUpdate
): Promise<OnboardingData> {
  return authorizedRequest(
    "/api/v1/onboarding/me",
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    }
  );
}


export interface KycRequirements {
  identity_documents: {
    selection: string;
    options: {
      code: string;
      name: string;
      description: string;
    }[];
  };
  guidelines: string[];
  uploads_enabled: boolean;
  verification_available: boolean;
}

export async function getKycRequirements():
  Promise<KycRequirements> {
  return authorizedRequest(
    "/api/v1/kyc/requirements"
  );
}
