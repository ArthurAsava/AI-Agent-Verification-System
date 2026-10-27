# SalesMesh Agent Verification — Database Architecture

## 1. Overview

The system uses Supabase PostgreSQL as its primary relational database. FastAPI accesses PostgreSQL through SQLAlchemy, while Alembic manages schema migrations.

## 2. Database Tables

| Table | Purpose |
|---|---|
| agents | Agent registration profiles and onboarding status |
| kyc_documents | Metadata and private storage references for identity documents |
| verification_checks | Results of OCR, biometric, identity, and manual verification |
| fraud_assessments | AI-assisted fraud risk scores and model versions |
| audit_logs | Security-relevant events and system activity |

Supabase Auth manages user identities in the `auth.users` table.

## 3. Security Controls

- Row-Level Security is enabled on all five application tables.
- Authenticated agents can read their own agent profile, document metadata, and verification statuses.
- Client-side modification permissions are not granted during Phase 4.
- Fraud assessments and audit logs are not exposed to ordinary authenticated users.
- Database administrator credentials remain server-side and must never be exposed to the frontend.
- Identity documents and biometric data must use restricted storage and appropriate retention controls.

## 4. Schema Management

Database schema changes are implemented through version-controlled Alembic migrations.

Before applying migrations, developers must review the generated SQL operations to ensure that Supabase-managed schemas are not modified.

## 5. Testing

Unit tests validate model structure. Integration tests verify database connectivity, application tables, migration state, and RLS configuration.

Future authorization tests will verify access isolation using nonprivileged authenticated identities.

## 6. Future Development

Phase 5 will implement Supabase Auth integration, agent registration, authenticated access, and role-based authorization.

Later phases will implement private document storage, OCR, biometric verification, AI-assisted fraud detection, and administrative review workflows.