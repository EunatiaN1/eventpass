"""FastAPI entry point for the EventPass backend & interactive web preview."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.routes.campaigns import router as campaigns_router
from backend.routes.checkin import router as checkin_router
from backend.routes.events import router as events_router
from backend.routes.ledger import router as ledger_router
from backend.routes.tickets import router as tickets_router
from backend.routes.webhooks import router as webhooks_router
from backend.routes.x402 import router as x402_router

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="EventPass API",
    description="EventPass ticketing, social resale campaigns, 75% unsold-ticket refunds, double-entry ledger, fiat webhooks, and x402 agent payments (Solana Devnet).",
    version="0.2.0",
)

app.include_router(events_router)
app.include_router(tickets_router)
app.include_router(campaigns_router)
app.include_router(checkin_router)
app.include_router(ledger_router)
app.include_router(webhooks_router)
app.include_router(x402_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_web_app() -> FileResponse:
    """Serve the interactive EventPass web application."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/c/{slug}", include_in_schema=False)
async def serve_campaign_deep_link(slug: str) -> FileResponse:
    """Serve the public social resale campaign landing page for a shareable slug."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Basic liveness check."""
    return {"status": "ok"}
