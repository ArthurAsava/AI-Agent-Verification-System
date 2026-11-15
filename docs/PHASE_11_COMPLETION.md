# Phase 11: Verification Administration Dashboard

## Objective

Make the completed verification workflow operationally usable by authorized
staff without moving authorization or fraud decisions into the browser.

## Delivered behavior

- `/admin` provides an administrator dashboard with aggregate workflow
  health: cases awaiting review, high/critical-risk open cases, submissions in
  the last 24 hours, agents under review, and active reviewers.
- The dashboard intentionally displays aggregate counts only; it does not
  expose identity documents, biometric media, KYC payloads, emails, or raw
  provider responses.
- Administrators can activate/deactivate reviewers and grant/revoke
  administrator capability for existing SalesMesh agent accounts using their
  UUID. Every access change creates an audit record.
- The backend prevents an administrator from removing their own active admin
  access and prevents removal of the final active administrator.
- Reviewer case details now render the Phase 10 reviewer-safe fraud assessment
  with rule explanations and sanitized count/threshold evidence.
- All administrator endpoints are protected by `require_admin`, which checks
  the server-side `verification_reviewers` record for both active and admin
  status. An active reviewer without admin capability receives `403`.

## Administrator provisioning

Alembic revision `ff2e99f8c987` adds `is_admin` to
`verification_reviewers`. It does not hard-code a person or email address.
The first administrator was provisioned in the active development database as
an existing, active reviewer. Future trusted deployments can use:

```powershell
cd backend
..\.venv\Scripts\python.exe scripts\bootstrap_verification_admin.py --user-id <existing-auth-user-uuid>
```

The utility accepts only an existing user UUID with a SalesMesh agent profile
and writes an audit event. It does not handle passwords or email addresses.

## Security boundary

- Browser UI is never the authorization authority; FastAPI verifies the
  authenticated user against the server database for each protected request.
- Fraud scores, KYC-provider outcomes, and dashboard metrics are decision
  support only. A human reviewer remains responsible for approve/reject/
  resubmission decisions.
- The Phase 11 migration makes no grants, table-exposure, RLS, or RLS-policy
  changes. Existing deferred RLS policy work remains outside this phase.

## Validation

- Backend regression suite validates administrator authorization, self-lockout
  prevention, final-admin protection, aggregate-only metrics, and existing
  reviewer decision security.
- Live transactional database checks verify the active admin role and
  aggregate summary against Supabase PostgreSQL.
- Frontend ESLint and strict TypeScript checks pass.
- The unauthenticated `/admin` route renders its expected sign-in boundary;
  authenticated browser testing is performed by signing in as the configured
  administrator, never by automating credentials.
