import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.api import (
    admin,
    analytics,
    auth,
    chat,
    comparison,
    expert,
    gis,
    groundwater,
    health,
    imports,
    notifications,
    predictions,
    push,
    quality,
    rag,
    reports,
    scenarios,
    voice,
    weather,
)
from app.config import get_settings
from app.database import Base, SessionLocal, engine

settings = get_settings()

_background_tasks: set[asyncio.Task] = set()


def _run_sync_in_thread(fn) -> None:
    """Run a blocking DB/network job (fn(db, ...)) off the event loop.

    Spawns a short-lived session, runs the job in a worker thread and closes
    the session afterwards, so requests and startup are never stalled by the
    knowledge ingestion, CSV refresh or live-data syncs.
    """

    def _target() -> None:
        db = SessionLocal()
        try:
            fn(db)
        except Exception:  # noqa: BLE001 - background syncs must never crash the app
            pass
        finally:
            db.close()

    _background_tasks.add(asyncio.create_task(asyncio.to_thread(_target)))


async def _live_sync_loop() -> None:
    interval = settings.LIVE_SYNC_INTERVAL_MINUTES * 60
    while True:
        await asyncio.sleep(interval)
        from app.ingres.live import sync_live_data

        _run_sync_in_thread(sync_live_data)


async def _digest_loop() -> None:
    """Process due scheduled reports (digests) on a fixed interval."""
    interval = max(settings.SCHEDULED_REPORTS_CHECK_MINUTES, 1) * 60
    while True:
        await asyncio.sleep(interval)
        from app.services.digests import process_due_schedules

        _run_sync_in_thread(process_due_schedules)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)
        from app.rag.retriever import ingest as rag_ingest

        _run_sync_in_thread(rag_ingest)
    if settings.SEED_REAL_DATA or settings.REAL_DATA_AUTO_REFRESH:
        from app.ingres.real_import import refresh_real_dataset

        _run_sync_in_thread(refresh_real_dataset)
    if settings.LIVE_DATA_ENABLED:
        # One sync right away, then periodically, without ever blocking startup.
        from app.ingres.live import sync_live_data

        _run_sync_in_thread(sync_live_data)
        _background_tasks.add(asyncio.create_task(_live_sync_loop()))
    if settings.QUALITY_SCAN_ON_BOOT:
        from app.services.data_quality import run_quality_scan

        _run_sync_in_thread(run_quality_scan)
    if settings.SCHEDULED_REPORTS_ENABLED:
        from app.services.digests import process_due_schedules

        _run_sync_in_thread(process_due_schedules)
        _background_tasks.add(asyncio.create_task(_digest_loop()))
    yield
    for task in list(_background_tasks):
        task.cancel()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# Compress large JSON payloads (e.g. the GIS map responses).
app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(groundwater.router, prefix=settings.API_PREFIX)
app.include_router(chat.router, prefix=settings.API_PREFIX)
app.include_router(gis.router, prefix=settings.API_PREFIX)
app.include_router(reports.router, prefix=settings.API_PREFIX)
app.include_router(analytics.router, prefix=settings.API_PREFIX)
app.include_router(comparison.router, prefix=settings.API_PREFIX)
app.include_router(quality.router, prefix=settings.API_PREFIX)
app.include_router(predictions.router, prefix=settings.API_PREFIX)
app.include_router(scenarios.router, prefix=settings.API_PREFIX)
app.include_router(expert.router, prefix=settings.API_PREFIX)
app.include_router(admin.router, prefix=settings.API_PREFIX)
app.include_router(voice.router, prefix=settings.API_PREFIX)
app.include_router(rag.router, prefix=settings.API_PREFIX)
app.include_router(imports.router, prefix=settings.API_PREFIX)
app.include_router(notifications.router, prefix=settings.API_PREFIX)
app.include_router(push.router, prefix=settings.API_PREFIX)
app.include_router(weather.router, prefix=settings.API_PREFIX)


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "tagline": "Indian Groundwater Resource Estimation AI Assistant",
        "docs": "/docs",
        "health": "/api/health",
    }