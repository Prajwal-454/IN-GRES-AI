from sqlalchemy import inspect

from app.config import get_settings
from app.database import Base, SessionLocal, engine

import app.models  # noqa: F401  (registers all tables on Base.metadata)


def init_local_schema() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_postgis() -> bool:
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.commit()
        return True
    except Exception:
        return False


def main() -> None:
    init_local_schema()
    print(f"Schema ready: {len(Base.metadata.tables)} tables")

    from app.database.seed import seed_demo_users

    with engine.connect() as conn:
        if not inspect(conn).has_table("users"):
            print("users table missing after create_all")
            return

    db = SessionLocal()
    try:
        seed_demo_users()

        seed_mode = get_settings().SEED_DATASET
        if seed_mode == "national":
            from app.ingres.national_seed import seed_national_groundwater

            per_district = get_settings().SEED_VILLAGES_PER_DISTRICT or None
            seed_national_groundwater(db, per_district=per_district)
        elif seed_mode == "demo":
            from app.ingres.demo_data import seed_demo_groundwater

            seed_demo_groundwater(db)
        else:
            print("SEED_DATASET=none: skipping demo data seeding")

        if get_settings().SEED_REAL_DATA:
            from app.ingres.real_import import import_real_dataset

            result = import_real_dataset(db)
            print(f"Real data import: {result}")
    finally:
        db.close()
    print("Local development database initialised")


if __name__ == "__main__":
    main()