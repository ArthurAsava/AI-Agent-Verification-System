# Phase 13: System Test and Evaluation

**Status:** complete on 16 November 2026

Phase 13 validates the implemented system against the functional, security,
integration, and rule-evaluation objectives in the project specification. It
does not represent a claim of production biometric accuracy: a separate,
approved labelled test corpus and live provider test run are required to make
that claim.

## Executed validation

| Gate | Command | Result |
| --- | --- | --- |
| Backend automated suite | `uv run --with-requirements requirements.txt pytest -m "not integration" -q` from `backend/` | **336 passed, 13 deselected** |
| Live development database | `RUN_DB_TESTS=1`, `RUN_VERIFICATION_DB_TESTS=1`, then the two database integration modules | **13 passed** in 34.67 seconds |
| Frontend static analysis | `npm run lint` from `frontend/` | **passed** |
| Frontend production compilation | `NEXT_DIST_DIR=.next-phase13-evaluation npm run build` | **passed**, 13 routes generated or partially prerendered |
| Guest browser smoke test | Local frontend at `http://localhost:3000` | **passed**; landing page, navigation, calls to action, and passport-profile surface rendered |
| JavaScript dependency audit | `npm audit --omit=dev --json` | **0 production vulnerabilities** |
| Python dependency audit | `pip-audit -r requirements.txt` | **no known vulnerabilities** |

The live database tests use an outer transaction and roll back the application
work created by each test. The one schema change made during this phase was
recorded in Alembic and applied normally; it removed one redundant index while
retaining the unique constraint that enforces one onboarding record per agent.

## Requirement coverage

| Requirement | Evidence |
| --- | --- |
| FR-01 registration and authentication | `test_auth.py`, `test_agent_service.py`, `test_onboarding_api.py` |
| FR-02 document submission | `test_kyc_upload_api.py`, `test_kyc_upload_service.py`, `test_file_validation.py` |
| FR-03 OCR and extraction | `test_ocr_service.py`, `test_identity_extractor.py`, `test_document_quality.py` |
| FR-04 configured KYC provider | `test_didit_service.py`, `test_didit_api_security.py` |
| FR-05 selfie upload | `test_biometric_selfie_upload.py` |
| FR-06 biometric review path | `test_biometric_review_service.py`, `test_biometric_review_api_security.py` |
| FR-07 fraud indicators | `test_fraud_rules.py`, `test_fraud_signal_service.py`, `test_risk_engine.py` |
| FR-08 verification result and risk persistence | `test_verification_persistence.py`, `test_verification_db_integration.py` |
| FR-09 reviewer access | `test_verification_api_security.py`, `test_verification_reviewer.py` |
| FR-10 approve or reject decision | `test_verification_decisions.py`, `test_verification_reviewer.py` |
| FR-11 access restrictions | API authorization tests, `test_security_hardening.py`, and live RLS/grant checks |
| FR-12 verification status | `test_verification_submission.py`, `test_verification_workflow.py` |
| FR-13 administrator record management | `test_verification_admin.py`, `test_verification_db_integration.py` |
| FR-14 aggregate reports | `test_verification_admin.py`, `test_verification_db_integration.py` |
| FR-15 audit records | `test_kyc_download_audit.py`, `test_verification_persistence.py`, and live audit tests |

## Evaluated scenarios

The automated suite exercises valid documents, malformed and over-size files,
MIME and filename spoofing, integrity checksum changes, partial and invalid OCR
extractions, identity matches and mismatches, quality failures, clean and
multi-signal fraud cases, unauthenticated and unauthorized requests, stale
review decisions, and failure rollbacks. The provider and biometric tests use
controlled responses; they do not submit a real person's document or selfie.

The fraud capability is intentionally rule-based and explainable rather than a
trained classification model. Its deterministic evaluations cover clean,
mismatched, unknown, and multi-signal inputs; its result is a risk score and
human-review recommendation, never an automatic final approval.

## Database and security findings

- The live suite confirmed connection, required tables, RLS on all protected
  public tables, expected policies, no direct `PUBLIC`, `anon`, or
  `authenticated` table grants, persistence/audit behavior, idempotency, and
  reviewer/administrator controls.
- Migration `d8e4f9a1c2b7` removes the duplicated unique index
  `ix_agent_onboarding_agent_id`. The constraint-backed
  `agent_onboarding_agent_id_key` remains, and a live regression test asserts
  it is the sole unique `agent_id` lookup.
- The Supabase health advisor returned no findings. Its security advisor still
  reports **Leaked Password Protection Disabled**. Enable it in Supabase Auth
  settings before a public release.
- Other database index notices are observational only on this very small
  development dataset. They should be reviewed using production query volume
  before removal; no useful index was removed merely because it has not yet
  received traffic.
- The test run has one upstream Starlette deprecation warning concerning its
  HTTPX test client. It does not fail tests; review the FastAPI/Starlette test
  client upgrade path during dependency maintenance.

## Metrics boundary

Verification accuracy, fraud-detection rate, false-accept rate (FAR),
false-reject rate (FRR), biometric spoof-detection rate, and realistic
end-to-end latency are **not reported**. The current fixtures prove control
flow and deterministic rule behavior, not statistically valid real-world
performance. Reporting those values would require:

1. a privacy-approved, labelled holdout set representing valid identities,
   document forgeries, and presentation attacks;
2. independent human adjudication and a fixed decision threshold;
3. recorded true/false positive and negative counts, including a documented
   confidence interval; and
4. load testing of the deployed API, database, storage, and provider callback
   path under an agreed concurrent-user profile.

## Continuous quality gate

`.github/workflows/quality.yml` now runs on every pull request to `main` and
every `main` push. It renders Alembic migrations, runs non-live backend tests,
audits Python dependencies, lints and production-builds the frontend, and
audits production JavaScript dependencies. Live Supabase tests remain an
explicit, rollback-isolated development-environment command so CI has no
database credentials or access to identity data.

## Phase 14 handoff

Before deploying publicly, enable Supabase leaked-password protection, use
production-only environment values in the deployment host, configure a public
HTTPS Didit webhook endpoint, and complete an authorized manual Didit sandbox
journey (success, rejection, expired session, and invalid webhook signature).
Then run the same test gates from this document against the release candidate.
