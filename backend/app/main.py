
from fastapi import FastAPI

app = FastAPI(
    title="AI Agent Verification System",
    description="Backend API for SalesMesh agent registration and verification",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "AI Agent Verification System API",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "backend",
    }
