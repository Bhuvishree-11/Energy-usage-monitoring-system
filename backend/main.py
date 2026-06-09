from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import os

from core.database import init_pool, close_pool

from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.buildings import router as buildings_router
from routers.devices import router as devices_router
from routers.usage import router as usage_router
from routers.alerts import router as alerts_router
from routers.reports_settings import reports_router, settings_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smartwatt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔌 Starting SmartWatt API – initialising DB pool…")
    init_pool()
    yield
    logger.info("🛑 Shutting down – closing DB pool…")
    close_pool()


app = FastAPI(
    title="SmartWatt API",
    description="""
    Backend for **SmartWatt** – Smart Building Energy Monitoring System.

    ## Pages served
    | Frontend page       | Main endpoints                              |
    |---------------------|---------------------------------------------|
    | Login               | `POST /auth/login`                          |
    | Dashboard           | `GET /dashboard/*`                          |
    | Buildings & Rooms   | `GET /buildings`, `/buildings/{id}/tree`    |
    | Devices             | `GET /buildings/{id}/devices`               |
    | Sensors             | `GET /sensors`, `POST /sensors/simulate`    |
    | Usage Records       | `GET /usage`, `GET /usage/export/csv`       |
    | Alerts              | `GET /alerts`, `POST /alerts/{id}/resolve`  |
    | Reports             | `POST /reports/{id}/generate`               |
    | Settings            | `GET /settings`, `PATCH /settings`          |

    ## Auth
    Use `POST /auth/login` with `admin@smartwatt.com / admin123` to get a JWT.
    Pass it as `Authorization: Bearer <token>` on every other request.
    """,
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS (allow your frontend origin) ───────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5500,null"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"file://.*",   # allow file:// for local HTML dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global error handler ─────────────────────────────────────────
@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Routers ──────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(buildings_router)
app.include_router(devices_router)
app.include_router(usage_router)
app.include_router(alerts_router)
app.include_router(reports_router)
app.include_router(settings_router)


# ── Health ───────────────────────────────────────────────────────
@app.get("/health", tags=["Meta"])
def health():
    return {"status": "ok", "service": "SmartWatt API", "version": "2.0.0"}


@app.get("/", tags=["Meta"])
def root():
    return {
        "message": "energy-monitoring-system API is running ⚡",
        "docs":    "/docs",
        "health":  "/health",
    }
