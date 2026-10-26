
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export interface HealthResponse {
  status: string;
  service: string;
}

export async function getBackendHealth(): Promise<HealthResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/health`,
    {
      method: "GET",
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      `Backend health check failed: ${response.status}`
    );
  }

  return (await response.json()) as HealthResponse;
}
