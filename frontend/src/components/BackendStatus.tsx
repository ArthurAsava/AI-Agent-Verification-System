
"use client";

import { useEffect, useState } from "react";

import {
  getBackendHealth,
  type HealthResponse,
} from "@/lib/api";

export default function BackendStatus() {
  const [health, setHealth] =
    useState<HealthResponse | null>(null);

  const [error, setError] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function checkBackend() {
      try {
        const result = await getBackendHealth();

        if (active) {
          setHealth(result);
        }
      } catch {
        if (active) {
          setError("Unable to connect to backend");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void checkBackend();

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <p>Checking backend connection...</p>;
  }

  if (error) {
    return <p style={{ color: "red" }}>{error}</p>;
  }

  return (
    <section>
      <h2>Backend Connection</h2>
      <p>Status: {health?.status}</p>
      <p>Service: {health?.service}</p>
    </section>
  );
}
