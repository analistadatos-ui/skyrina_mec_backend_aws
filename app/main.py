from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.middleware.base import BaseHTTPMiddleware
from mangum import Mangum  # <-- Lambda adapter
import logging
import os

from sqlalchemy import text
from app.database import engine, Base, get_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import all models (so SQLAlchemy is aware of them)
from app.models.user_model import User
from app.models.linea_model import Linea
from app.models.ticket_model import Ticket
from app.models.ticket_falla_model import TicketFallaEquipo
from app.models.ticket_cambio_model import TicketCambioEstilo
from app.models.ticket_asignacion_model import TicketAsignacion
from app.models.falla_equipo_model import FallaEquipo
from app.models.cambio_estilo_model import CambioEstilo
from app.models.ticket_historial_model import TicketHistorial
from app.models.ticket_comentario_model import TicketComentario

# Import routes
from app.routes import auth_routes, supervisor_routes, ticket_routes
from app.routes.mecanico_routes import router as mecanico_router
from app.routes.jefe_mecanicos_routes import router as jefe_mecanicos_router
from app.routes.rh_routes import router as rh_router

# Configuration from environment
API_PREFIX = os.getenv("API_PREFIX", "/api/v1")
ENABLE_HTTPS_REDIRECT = os.getenv("ENABLE_HTTPS_REDIRECT", "true").lower() == "true"
HSTS_MAX_AGE = int(os.getenv("HSTS_MAX_AGE", "31536000"))

# CORS origins from env (comma-separated). Set CORS_ORIGINS in Lambda to your
# CloudFront/frontend URL, e.g. https://xxxx.cloudfront.net
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
)
ALLOW_ORIGINS = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]

# ------------------------------------------------------------------
# NOTE for Lambda:
#  - No lifespan / startup DB check (would run on every cold start).
#  - No Base.metadata.create_all (tables created once via migrate_once.py).
#  - No StaticFiles("/uploads") mount (Lambda has no persistent disk;
#    uploads go to S3 via app/core/s3.py).
# ------------------------------------------------------------------

app = FastAPI(
    title="Skyrina Mechanics API",
    description="Production-ready API for mechanics management system",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=f"{API_PREFIX}/openapi.json",
)


# Custom Swagger docs endpoint
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if ENABLE_HTTPS_REDIRECT:
            response.headers["Strict-Transport-Security"] = f"max-age={HSTS_MAX_AGE}"
        return response


app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
    expose_headers=["Content-Length", "X-Process-Time"],
    max_age=3600,
)

# Include routers
app.include_router(auth_routes.router, prefix=API_PREFIX, tags=["Authentication"])
app.include_router(supervisor_routes.router, prefix=API_PREFIX, tags=["Supervisor"])
app.include_router(mecanico_router, prefix=API_PREFIX, tags=["Mechanic"])
app.include_router(ticket_routes.router, prefix=API_PREFIX, tags=["Tickets"])
app.include_router(jefe_mecanicos_router, prefix=API_PREFIX, tags=["Head Mechanic"])
app.include_router(rh_router, prefix=API_PREFIX, tags=["RH"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Skyrina Mechanics API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "api_prefix": API_PREFIX,
    }


@app.get(f"{API_PREFIX}/health", tags=["Health"])
async def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "service": "operational"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unavailable")


# ------------------------------------------------------------------
# Lambda entry point. API Gateway -> Lambda invokes this handler.
# ------------------------------------------------------------------
handler = Mangum(app)