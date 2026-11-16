# Phase 12: Production Security Hardening

## Completed controls

- Closed the Supabase public-table Data API surface. The browser continues to
  use Supabase Auth, while every application-data operation goes through the
  authenticated FastAPI API.
- Enabled RLS for every public application table and `alembic_version`.
- Revoked `PUBLIC`, `anon`, and `authenticated` table privileges from the
  application and migration tables. The FastAPI database role is the trusted
  server-side access path.
- Added restrictive, deny-by-default RLS policies for audit logs, fraud
  assessments, reviewer records, and Alembic migration metadata.
- Verified the private `agent-kyc-documents` Storage bucket remains private;
  it has no client object policies and is accessed only by the backend service
  role after application authorization checks.
- Added explicit CORS origin and trusted-host allowlists. Wildcard values are
  rejected at startup.
- Made production startup fail closed unless HTTPS enforcement is enabled,
  debug mode is off, and public frontend/Didit URLs use HTTPS.
- Added API security headers, no-store caching for authenticated API routes,
  bounded bearer-token validation, and a bounded per-process rate limiter.
- Added frontend security headers, including a production HSTS header and a
  CSP that permits the Supabase and API HTTPS connections used by the app.
- Disabled interactive FastAPI docs and OpenAPI routes automatically when
  `APP_ENV=production`.

## Production configuration

Set the backend environment before deploying:

```dotenv
APP_ENV=production
DEBUG=false
FRONTEND_URL=https://app.example.com
CORS_ALLOWED_ORIGINS=https://app.example.com
TRUSTED_HOSTS=api.example.com
ENFORCE_HTTPS=true
TRUST_PROXY_HEADERS=true
```

Only set `TRUST_PROXY_HEADERS=true` when the API is behind a trusted reverse
proxy that strips client-supplied forwarding headers and supplies its own.
The included limiter protects a single FastAPI process. Configure equivalent
rate limits at the production load balancer/API gateway when running more than
one process or instance.

For a production Didit integration, also set `DIDIT_ENVIRONMENT=production`
and use an HTTPS `DIDIT_RETURN_URL`. The backend refuses an unsafe production
combination at startup.

## Remaining Supabase dashboard action

Supabase reports one account-level warning that cannot be changed by a schema
migration: **Leaked password protection** is disabled. An account owner should
enable it in the Supabase Authentication password-security settings, then
re-run the Supabase Security Advisor. This turns on compromised-password
screening during password signup and reset. See the
[Supabase password-security documentation](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

## Verification

- Targeted backend hardening tests: 17 passed.
- Live PostgreSQL security integration tests: 6 passed.
- Supabase Security Advisor: all RLS and public-table findings resolved; only
  the account-level leaked-password-protection warning remains.
