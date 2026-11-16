
# AI-Enabled Agent Registration & Verification System

An AI-powered registration and identity verification
system developed for the SalesMesh platform.

## Features

- Agent registration and authentication
- Identity document verification
- Biometric face verification
- KYC verification
- AI-assisted fraud detection
- Administrator dashboard
- Role-based access control

## Technology Stack

### Frontend
- Next.js
- TypeScript

### Backend
- Python
- FastAPI

### Database and Authentication
- Supabase PostgreSQL
- Supabase Auth
- Supabase Storage

### Artificial Intelligence
- EasyOCR
- OpenCV
- DeepFace
- Scikit-learn

## Project Structure

- backend/ - FastAPI backend
- frontend/ - Next.js frontend
- database/ - Database migrations and scripts
- docs/ - Project documentation
- scripts/ - Development utilities

## Current Progress

Phase 12 - Production security hardening complete.

The verification subsystem now includes document and provider evidence,
explainable fraud signals, human review queues, server-enforced reviewer and
administrator access, an aggregate administration dashboard, and a
server-only application-data boundary. See the phase completion notes in
`docs/` for the operational boundaries, production configuration, and release
checks.

## Security

Never commit credentials, environment secrets,
identity documents, or biometric data to GitHub.
