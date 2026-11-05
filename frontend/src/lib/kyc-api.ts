
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
  const response = await fetch(
    `${API_URL}${path}`,
    {
      ...options,
      headers,
      cache: "no-store",
    }
  );

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

export async function downloadKycDocument(
  documentId: string
): Promise<Blob> {
  const response = await authenticatedRequest(
    `/api/v1/kyc/documents/${encodeURIComponent(documentId)}/download`
  );

  return response.blob();
}
