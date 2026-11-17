
import { createClient } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export interface KycDocument {
  document_id: string;
  agent_id: string;
  document_type: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  status: string;
  biometric_check_id?: string | null;
}

export interface VerificationSubmission {
  case_id: string;
  status: string;
  message: string;
}

export class KycApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "KycApiError";
  }
}

async function authenticatedRequest(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const supabase = createClient();

  const { data, error } =
    await supabase.auth.getSession();

  if (error || !data.session) {
    throw new KycApiError(
      "Please sign in first",
      401
    );
  }

  const headers = new Headers(options.headers);

  headers.set(
    "Authorization",
    `Bearer ${data.session.access_token}`
  );

  // Do not manually set Content-Type for FormData.
  // The browser must add the multipart boundary.
  let response: Response;

  try {
    response = await fetch(
      `${API_URL}${path}`,
      {
      ...options,
      headers,
      cache: "no-store",
      },
    );
  } catch {
    throw new KycApiError(
      "Verity could not reach its local API. Start the backend on port 8000, then refresh this page.",
      0,
    );
  }

  if (!response.ok) {
    let message =
      `Request failed: ${response.status}`;

    try {
      const body: unknown = await response.json();

      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body &&
        typeof body.detail === "string"
      ) {
        message = body.detail;
      }
    } catch {
      // Keep the generic HTTP error message.
    }

    throw new KycApiError(
      message,
      response.status
    );
  }

  return response;
}

export async function listKycDocuments():
  Promise<KycDocument[]> {
  const response = await authenticatedRequest(
    "/api/v1/kyc/documents"
  );

  return response.json() as Promise<KycDocument[]>;
}

export async function getKycDocument(
  documentId: string
): Promise<KycDocument> {
  const response = await authenticatedRequest(
    `/api/v1/kyc/documents/${encodeURIComponent(documentId)}`
  );

  return response.json() as Promise<KycDocument>;
}

export async function uploadKycDocument(
  documentType: string,
  file: File
): Promise<KycDocument> {
  const formData = new FormData();

  formData.append("document_type", documentType);
  formData.append("file", file);

  const response = await authenticatedRequest(
    "/api/v1/kyc/documents",
    {
      method: "POST",
      body: formData,
    }
  );

  return response.json() as Promise<KycDocument>;
}

export async function uploadBiometricSelfie(
  file: File,
): Promise<KycDocument> {
  const formData = new FormData();

  formData.append("consent", "true");
  formData.append("file", file);

  const response = await authenticatedRequest(
    "/api/v1/kyc/documents/biometric-selfie",
    {
      method: "POST",
      body: formData,
    }
  );

  return response.json() as Promise<KycDocument>;
}

export interface DiditSession {
  check_id: string;
  provider: "didit";
  session_id: string;
  verification_url: string;
  status: string;
}

export interface DiditKycStatus {
  check_id: string;
  check_status: string;
  provider_status: string | null;
  is_final: boolean | null;
  actions: Record<string, string>;
  synced_at: string | null;
}

interface DiditKycStatusResponse {
  check: DiditKycStatus | null;
}

export async function startDiditSession(): Promise<DiditSession> {
  const response = await authenticatedRequest(
    "/api/v1/biometric/didit/sessions",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ biometric_consent: true }),
    },
  );

  return response.json() as Promise<DiditSession>;
}

export async function getDiditKycStatus(): Promise<DiditKycStatus | null> {
  const response = await authenticatedRequest(
    "/api/v1/biometric/didit/status",
  );

  const body = await response.json() as DiditKycStatusResponse;
  return body.check;
}

export async function downloadKycDocument(
  documentId: string
): Promise<Blob> {
  const response = await authenticatedRequest(
    `/api/v1/kyc/documents/${encodeURIComponent(documentId)}/download`
  );

  return response.blob();
}

export async function submitKycDocumentForVerification(
  documentId: string
): Promise<VerificationSubmission> {
  const response = await authenticatedRequest(
    `/verification/documents/${encodeURIComponent(documentId)}/submit`,
    {
      method: "POST",
    }
  );

  return response.json() as Promise<VerificationSubmission>;
}
