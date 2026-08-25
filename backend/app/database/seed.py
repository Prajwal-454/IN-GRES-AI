from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_password
from app.database import SessionLocal, engine
from app.models.user import User

settings = get_settings()


def _ensure_user(db: Session, email: str, full_name: str, password: str, role: str) -> None:
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        return
    db.add(
        User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
        )
    )


def seed_demo_users() -> None:
    with engine.connect() as conn:
        if not inspect(conn).has_table("users"):
            print("users table not present; run `alembic upgrade head` before seeding")
            return

    db = SessionLocal()
    try:
        _ensure_user(
            db,
            settings.SEED_ADMIN_EMAIL,
            "IN-GRES Administrator",
            settings.SEED_ADMIN_PASSWORD,
            "admin",
        )
        _ensure_user(
            db,
            settings.SEED_USER_EMAIL,
            "Demo Groundwater User",
            settings.SEED_USER_PASSWORD,
            "user",
        )
        db.commit()
        print(f"Seeded demo users ({settings.SEED_ADMIN_EMAIL} / {settings.SEED_USER_EMAIL})")
    finally:
        db.close()


def seed_groundwater_data() -> None:
    """Seed the configured demo dataset (national by default)."""
    from app.database import SessionLocal as _SessionLocal

    mode = settings.SEED_DATASET
    if mode == "none":
        print("SEED_DATASET=none: skipping groundwater demo data")
        return

    db = _SessionLocal()
    try:
        if mode == "national":
            from app.ingres.national_seed import seed_national_groundwater

            seed_national_groundwater(db, per_district=settings.SEED_VILLAGES_PER_DISTRICT or None)
        else:
            from app.ingres.demo_data import seed_demo_groundwater

            seed_demo_groundwater(db)
    finally:
        db.close()


def main() -> None:
    seed_demo_users()
    seed_groundwater_data()


if __name__ == "__main__":
    main()