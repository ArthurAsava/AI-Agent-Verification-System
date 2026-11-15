# Didit Sandbox Setup

## Scope

Phase 8.3 uses Didit's hosted verification experience. SalesMesh creates a
session only after the agent gives separate consent, then redirects the agent
to Didit for document, selfie, and liveness capture. SalesMesh does not send a
locally stored selfie to Didit and does not retain Didit's media URLs or raw
verification payloads.

The signed Didit webhook is reduced to session and feature statuses in
`verification_checks.result_data`. A SalesMesh reviewer still records the
final decision; a provider result never changes `Agent.status` automatically.

## Configure the sandbox

1. Create a Didit account at `business.didit.me` and switch the application to
   **Sandbox**.
2. In **Identity verification → Workflows**, create a workflow with the checks
   you need. For actual liveness testing, select **Active Liveness**; passive
   liveness is not equivalent.
3. Copy the sandbox API key and workflow ID. Run the webhook-only proxy before
   starting a temporary public tunnel. This deliberately avoids exposing the
   full local API:

   ```powershell
   cd backend
   ..\.venv\Scripts\python.exe -m uvicorn scripts.didit_webhook_proxy:app --host 127.0.0.1 --port 8001
   ```

   Create a webhook destination for `status.updated`, pointing at:

   ```text
   https://<public-proxy-host>/api/v1/biometric/didit/webhook
   ```

   Copy that destination's signing secret.
4. Add these values only to the backend's untracked `.env` file:

   ```dotenv
   DIDIT_ENABLED=true
   DIDIT_API_KEY=<sandbox-api-key>
   DIDIT_WORKFLOW_ID=<sandbox-workflow-uuid>
   DIDIT_WEBHOOK_SECRET=<webhook-destination-secret>
   DIDIT_RETURN_URL=http://localhost:3000/dashboard/verification
   DIDIT_ENVIRONMENT=sandbox
   ```

   The return URL must be in Didit's allowed domains. In production it must
   use HTTPS. The webhook URL must be public HTTPS; tunnel port 8001 (the
   proxy), not port 8000 (the full API), while running locally. Never commit
   these values or expose them through a `NEXT_PUBLIC_` variable.
5. Restart the backend. Do not paste API keys or webhook secrets into chat.

## Sandbox verification flow

1. Sign in as an agent and select **Start Didit verification** after reading
   and accepting the Didit biometric-consent notice.
2. SalesMesh creates a session with an opaque internal identifier and redirects
   the browser to the URL Didit returned.
3. Complete the hosted sandbox flow with Didit's test data and scenario tools,
   not real identity or biometric data.
4. Didit sends its HMAC-signed `status.updated` webhook. SalesMesh verifies
   `X-Timestamp` and `X-Signature-V2`, deduplicates its event ID, and records
   only limited statuses for the reviewer.
5. A reviewer records the final SalesMesh biometric decision.

## Before production

- Agree Didit's data residency, retention, deletion, and subprocessor terms.
- Enable RLS and finish Storage access-policy hardening before processing real
  biometric data.
- Register production HTTPS return and webhook URLs, then use a production
  API key and workflow.
- Test declined, in-review, and signed-webhook failure paths before enabling
  real users.
