import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .database import ensure_database
from .routes import router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database schema and tables are active
    ensure_database()
    yield
    # Shutdown logic (if any)

app = FastAPI(
    title="Apex Logistics - Freight Claim Decision Engine API",
    description=(
        "Production REST API for automated B2B cargo refund evaluations, "
        "AI reasoning engine, SLA compliance logging, and auditor oversight."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for dashboard web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "online",
        "service": "Apex Claim Decision Engine",
        "version": "1.0.0",
        "database": "sqlite3",
    }

# Include core API routes under /api/v1
app.include_router(router, prefix="/api/v1", tags=["Decision Engine"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
