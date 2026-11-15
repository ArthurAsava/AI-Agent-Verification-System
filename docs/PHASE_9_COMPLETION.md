# Phase 9: KYC Verification Integration

## Objective

Connect the selected identity provider, Didit, to the SalesMesh KYC record so
that a signed provider event leads to an authoritative, minimized KYC outcome
for the correct agent. The provider result remains evidence for a human
reviewer; it never approves an agent automatically.

## Implementation

- SalesMesh creates a hosted Didit KYC session only after separate consent.
- The existing signed `status.updated` webhook validates `X-Timestamp` and
  `X-Signature-V2` before any provider API call.
- After validation, the backend retrieves the current Didit decision at
  `GET /v3/session/{session_id}/decision/` using the server-only API key.
- The persisted summary includes only provider status, finality, supported
  feature statuses, and a synchronization timestamp.
- Names, dates of birth, document numbers, contact details, media URLs, and
  raw provider decision payloads are deliberately excluded.
- An authenticated agent can read only their own minimized KYC status through
  `GET /api/v1/biometric/didit/status`.
- The agent verification dashboard displays the provider outcome and makes
  clear that a SalesMesh human review is still required.

## Failure and Retry Behavior

- A bad webhook signature is rejected.
- A missing local provider session is rejected.
- Provider retrieval failures return `503`; Didit can retry the signed event.
- A successfully synchronized event is idempotent and does not fetch or write
  the decision again.
- Provider data never changes `VerificationCheck.status` or `Agent.status`
  automatically.

## Database Impact

No migration is required. Phase 9 uses the existing `verification_checks`
record and its constrained provider evidence field. The active Supabase
database is at Alembic revision `c9447ad1e6f0`, which matches the repository
head.

## Validation

- Backend regression suite: 306 passed.
- Targeted Didit service and API security tests: 13 passed.
- Frontend ESLint: passed.
- Frontend TypeScript check: passed.
- Live Supabase schema/security integration checks: 5 passed.
- Live Supabase transaction-rollback integration checks: 4 passed.

## Release Boundary

The implementation is complete. One consent-gated sandbox verification remains
for the release checklist: an agent must initiate the hosted flow, choose test
data, and complete liveness capture. This creates the first real provider
session and validates the configured public webhook end to end. It cannot be
performed by the backend or by an administrator on an agent's behalf.

Supabase RLS-policy work remains intentionally deferred by project direction.
It must be resolved before processing real biometric or identity data in
production.
