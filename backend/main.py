"""FastAPI entry point for the EventPass backend – production-hardened."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_settings
from backend.rate_limit import limiter
from backend.routes.auth import router as auth_router
from backend.routes.campaigns import router as campaigns_router
from backend.routes.checkin import router as checkin_router
from backend.routes.events import router as events_router
from backend.routes.ledger import router as ledger_router\nfrom backend.routes.payfast import router as payfast_router
from backend.routes.mock_payments import router as mock_payments_router
from backend.routes.tickets import router as tickets_router
from backend.routes.webhooks import router as webhooks_router
from backend.routes.x402 import router as x402_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Refuse unsafe production defaults before serving any request."""
    if settings.environment == "production":
        missing = []
        if settings.use_dev_store:
            missing.append("SUPABASE_URL and SUPABASE_KEY")
        if not settings.resend_api_key:
            missing.append("RESEND_API_KEY")
        if (
            settings.jwt_secret == "devnet-jwt-secret-change-in-production-min-32-chars"
            or len(settings.jwt_secret) < 32
        ):
            missing.append("a unique JWT_SECRET of at least 32 characters")
        if missing:
            raise RuntimeError(
                "Production backend configuration is incomplete: " + ", ".join(missing)
            )
    yield


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject OWASP-recommended security headers on every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
settings = get_settings()

app = FastAPI(
    title="EventPass API",
    description=(
        "EventPass ticketing, social resale campaigns, 75% unsold-ticket refunds, "
        "double-entry ledger, fiat webhooks, and x402 agent payments (Solana Devnet)."
    ),
    version="0.3.0",
    lifespan=lifespan,
    # Never expose OpenAPI docs in production
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# ---------------------------------------------------------------------------
# SlowAPI global rate limiter
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Security headers (innermost – applied before CORS)
# ---------------------------------------------------------------------------
app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# CORS – strict allowlist, never wildcard
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "PAYMENT-SIGNATURE", "X-Auth-Client"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(tickets_router)
app.include_router(campaigns_router)
app.include_router(checkin_router)
app.include_router(ledger_router)
app.include_router(mock_payments_router)
app.include_router(webhooks_router)\napp.include_router(payfast_router)
app.include_router(x402_router)

# ---------------------------------------------------------------------------
# Static files & SPA catch-all
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_web_app() -> FileResponse:
    """Serve the interactive EventPass web application."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/c/{slug}", include_in_schema=False)
async def serve_campaign_deep_link(slug: str) -> FileResponse:
    """Serve the public social resale campaign landing page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Basic liveness check."""
    return {"status": "ok"}
