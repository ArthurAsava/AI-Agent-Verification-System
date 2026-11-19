import type { NextConfig } from "next";

const scriptSources = ["'self'", "'unsafe-inline'"];
const connectSources = ["'self'", "https:"];
const localApiOrigins = ["http://127.0.0.1:8000", "http://localhost:8000"];
const apiRunsLocally =
  process.env.NEXT_PUBLIC_API_URL?.startsWith("http://127.0.0.1:") ||
  process.env.NEXT_PUBLIC_API_URL?.startsWith("http://localhost:");

// React's development runtime uses eval to reconstruct component call stacks.
// Keep this development-only: production never receives unsafe-eval.
if (process.env.NODE_ENV !== "production") {
  scriptSources.push("'unsafe-eval'");
}

// The local FastAPI service is a separate origin. Keep HTTP access scoped to
// development and to local production-build checks; deployed APIs use HTTPS.
if (process.env.NODE_ENV !== "production" || apiRunsLocally) {
  connectSources.push(...localApiOrigins);
}

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(self), microphone=(), geolocation=(), payment=()",
  },
  {
    key: "Content-Security-Policy",
    value:
      "default-src 'self'; " +
      `script-src ${scriptSources.join(" ")}; ` +
      "style-src 'self' 'unsafe-inline'; " +
      "img-src 'self' data: blob: https:; " +
      `connect-src ${connectSources.join(" ")}; ` +
      "font-src 'self' data:; " +
      "object-src 'none'; base-uri 'self'; " +
      "frame-ancestors 'none'; form-action 'self'",
  },
];

if (process.env.NODE_ENV === "production") {
  securityHeaders.push({
    key: "Strict-Transport-Security",
    value: "max-age=31536000; includeSubDomains",
  });
}

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  cacheComponents: true,
  partialPrefetching: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
