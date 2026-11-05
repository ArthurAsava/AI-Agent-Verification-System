
from fastapi import APIRouter

from app.api.routes import demo, health, auth, agents, onboarding, kyc_requirements, kyc_documents

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(demo.router)
api_router.include_router(agents.router)
api_router.include_router(onboarding.router)
api_router.include_router(kyc_requirements.router)
api_router.include_router(kyc_documents.router)