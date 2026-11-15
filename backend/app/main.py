
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppException, app_exception_handler
from app.api.routes.verification import router as verification_router
from app.api.routes.biometric_review import (
    router as biometric_review_router,
)

import logging
from app.core.logging_config import configure_logging


settings = get_settings()

configure_logging(
    "DEBUG" if settings.DEBUG else "INFO"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Backend API for SalesMesh agent registration "
        "and identity verification."
    ),
    version="0.1.0",
    debug=settings.DEBUG,
)

app.include_router(verification_router)
app.include_router(biometric_review_router)

app.add_exception_handler(
    AppException,
    app_exception_handler,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX,
)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": settings.APP_NAME,
        "status": "running",
        "version": "0.1.0",
    }

logger.info("FastAPI application configured")
