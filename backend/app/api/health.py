from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database import engine

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
def health():
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }