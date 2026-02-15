import os
import sys

# Ensure the project root is in sys.path when executed directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.api.routes import router as api_router

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("bank_statement_intel.main")

app = FastAPI(
    title="Bank Statement Intelligence API",
    description=(
        "Production-grade pipeline for parsing PDF statements, categorizing transactions, "
        "and performing underwriting evaluations using rule-based heuristics and LLMs."
    ),
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Register routes
app.include_router(api_router)

@app.get("/")
def read_root():
    """
    Root endpoint redirecting to documentation.
    """
    return {
        "message": "Welcome to Bank Statement Intelligence API",
        "docs_url": "/docs",
        "health_url": "/api/v1/health"
    }

if __name__ == "__main__":
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}...")
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
