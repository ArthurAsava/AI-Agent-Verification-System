Overview: Purpose of the onboarding workflow.



Architecture: Next.js → FastAPI → PostgreSQL.



Database design: agent_onboarding and its relationship to agents.



Progress calculation: Five required fields, each worth 20%.



API endpoints: GET/PATCH onboarding and GET KYC requirements.



Security: Supabase Auth, ownership checks, RLS, and restrictions on changing verification status.



Frontend workflow: Three onboarding steps.



Testing: Unit, API, database, and two-account isolation tests.



Limitations: No document uploads, OCR, biometrics, or automated approval in Phase 6.