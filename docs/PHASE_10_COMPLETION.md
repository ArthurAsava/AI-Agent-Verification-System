# Phase 10: Explainable Fraud-Signal Detection

## Objective

Provide a useful fraud-detection baseline for SalesMesh verification without
making a black-box eligibility decision. Phase 10 is an explainable,
rules-based system, not a trained machine-learning model. Every assessment is
evidence for a human reviewer and never an automatic approval or rejection.

## Delivered behavior

At document submission, the trusted backend combines document-analysis signals
with bounded, data-minimized database and KYC-provider evidence. The resulting
assessment is stored with its rule codes, explanations, numeric weights, and
safe count/threshold context. The same safe inputs create the same opaque
assessment key, so retries do not create duplicate evidence.

| Signal | Rule code | Weight | Evidence retained |
| --- | --- | ---: | --- |
| Document identity mismatch | `IDENTITY_MISMATCH` | 45 | Rule code only |
| Document identity unknown | `IDENTITY_UNKNOWN` | 15 | Rule code only |
| Document-quality concern | `DOCUMENT_QUALITY_*` | 10–20 | Rule code only |
| Missing/conflicting identity fields | `MISSING_REQUIRED_FIELDS` / `CONFLICTING_IDENTITY_FIELDS` | 15 / 30 | Rule code only |
| Same checksum on another agent's document | `DUPLICATE_DOCUMENT` | 45 | Number of matching other-agent documents |
| Repeated failed document checks | `REPEATED_FAILURES` | 20 | Count, threshold (3), 24-hour window |
| Unusual submission frequency | `UNUSUAL_VERIFICATION_FREQUENCY` | 20 | Count, threshold (4), 24-hour window |
| Didit KYC decline | `PROVIDER_KYC_DECLINED` | 35 | Rule code only |
| Didit liveness/identity failure | `PROVIDER_LIVENESS_FAILURE` / `PROVIDER_IDENTITY_CHECK_FAILURE` | 30 | Rule code only |

Scores are capped at 100 and classified as low, medium, high, or critical.
Any non-clean or incomplete result requires human review. The policy thresholds
and weights are versioned as `risk-rules-v2` and must be calibrated against
reviewed outcomes before they are used to measure real-world fraud rates.

## Provider-event refresh

When a signed Didit webhook synchronizes a later KYC decision, SalesMesh
reassesses the latest Phase 10 case that is still awaiting review. The service
reconstructs only the prior safe rule baseline, merges the newly minimized
provider status, creates a new idempotent assessment if the result changed,
and updates the case recommendation. It does not change the case decision,
agent status, or access state.

## Reviewer evidence

`GET /api/v1/verification/cases/{case_id}` now returns the latest linked
`fraud_assessment` only to an authorized reviewer. It contains the risk level,
scoring version, review requirement, and sanitized signal list. Agents do not
receive these cross-agent fraud details through `GET /verification/me`.

The assessment deliberately excludes:

- Raw document checksums, document content, OCR text, identity fields, and
  other-agent identifiers.
- Biometric media, provider session IDs, raw Didit responses, and provider
  identity attributes.
- Any claim that a score proves fraud.

## Database migration

Alembic revision `b7a42540fab0` adds to `fraud_assessments`:

- `verification_case_id` with `ON DELETE SET NULL`.
- A unique opaque `assessment_key` for idempotency.
- `signals` JSONB and `requires_review` for reviewer-safe explanations.
- Targeted indexes for case assessment lookup and existing document checksum
  lookup.

It makes no table-exposure, grants, RLS, or RLS-policy changes.

## Validation

- Unit and API security coverage verifies rule thresholds, provider-summary
  parsing, idempotent persistence, reviewer-only evidence, and the invariant
  that provider refreshes cannot change agent state.
- Live transactional database coverage verifies the migration, sanitized JSONB
  evidence, and idempotent assessment-key behavior. The suite rolls back its
  test data.
- Backend regression suite: 316 passed, 10 skipped; live transactional suite:
  5 passed.
- Frontend ESLint and TypeScript checks passed.

## Operational boundary

This baseline is designed to prioritize review, not autonomous enforcement.
Before relying on it in production, SalesMesh needs a documented reviewer
feedback process, monitored false-positive/false-negative rates, and a formal
policy owner for threshold changes. Existing deferred RLS-policy work remains
outside this phase and must be completed before production identity or
biometric processing.
