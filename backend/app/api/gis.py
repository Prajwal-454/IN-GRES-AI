from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.gis import service
from app.models.groundwater import AssessmentUnit, District, State, Village
from app.models.user import User

router = APIRouter(prefix="/gis", tags=["gis"])


@router.get("/search")
def gis_search(
    q: str = Query(default="", min_length=1, max_length=120),
    limit: int = Query(default=10, ge=1, le=25),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Search states, districts, villages and assessment units by name.

    Returns the top matches with their scope names and coordinates so the map
    can zoom to a searched place.
    """
    needle = f"%{q.strip().lower()}%"
    results: list[dict] = []

    if len(q.strip()) >= 2:
        states = db.execute(
            select(State).where(func.lower(State.name).like(needle)).order_by(State.name).limit(limit)
        ).scalars().all()
        for s in states:
            results.append(
                {
                    "type": "state",
                    "name": s.name,
                    "state": s.name,
                    "district": None,
                    "village": None,
                    "latitude": None,
                    "longitude": None,
                }
            )

        districts = db.execute(
            select(District)
            .join(State, District.state_id == State.id)
            .where(func.lower(District.name).like(needle))
            .order_by(State.name, District.name)
            .limit(limit)
        ).scalars().all()
        for d in districts:
            results.append(
                {
                    "type": "district",
                    "name": d.name,
                    "state": d.state.name,
                    "district": d.name,
                    "village": None,
                    "latitude": None,
                    "longitude": None,
                }
            )

        villages = db.execute(
            select(Village, District, State)
            .join(District, Village.district_id == District.id)
            .join(State, District.state_id == State.id)
            .where(func.lower(Village.name).like(needle))
            .order_by(State.name, District.name, Village.name)
            .limit(limit)
        ).all()
        for v, d, s in villages:
            results.append(
                {
                    "type": "village",
                    "name": v.name,
                    "state": s.name,
                    "district": d.name,
                    "village": v.name,
                    "latitude": v.latitude,
                    "longitude": v.longitude,
                }
            )

        units = db.execute(
            select(AssessmentUnit, District, State)
            .join(District, AssessmentUnit.district_id == District.id)
            .join(State, AssessmentUnit.state_id == State.id)
            .where(func.lower(AssessmentUnit.name).like(needle))
            .order_by(State.name, District.name, AssessmentUnit.name)
            .limit(limit)
        ).all()
        for u, d, s in units:
            results.append(
                {
                    "type": "assessment_unit",
                    "name": u.name,
                    "state": s.name,
                    "district": d.name,
                    "village": None,
                    "latitude": u.latitude,
                    "longitude": u.longitude,
                }
            )

    return {"query": q, "results": results[: limit * 4]}


@router.get("/map")
def gis_map(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    metric: str = Query(default="stage"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return service.build_geojson(
        db, state=state, district=district, village=village, year=year, metric=metric
    )


@router.get("/india")
def gis_india(
    year: int | None = Query(default=None),
    metric: str = Query(default="stage"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return service.build_india_geojson(db, year=year, metric=metric)


@router.get("/units")
def gis_units(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return service.unit_centroids(db, state=state, district=district, village=village)


@router.get("/stations")
def gis_stations(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Synthetic monitoring-station points (placed district centroids)."""
    return service.unit_centroids(db, state=state, district=district, village=village)


@router.get("/analyze")
def gis_analyze(
    lat: float = Query(...),
    lon: float = Query(...),
    year: int | None = Query(default=None),
    target_year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """AI analysis for a clicked map location (status, water level, trend,
    risk, prediction and recommendations)."""
    return service.analyze_location(db, lat, lon, year=year, target_year=target_year)


@router.get("/prediction")
def gis_prediction(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year: int | None = Query(default=None),
    target_year: int | None = Query(default=None),
    metric: str = Query(default="stage"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return service.build_prediction_geojson(
        db,
        state=state,
        district=district,
        village=village,
        year=year,
        target_year=target_year,
        metric=metric,
    )


@router.get("/basins")
def gis_basins(
    basin: str | None = Query(default=None),
    year: int | None = Query(default=None),
    metric: str = Query(default="stage"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """River-basin choropleth aggregating the districts of each basin."""
    return service.build_basin_geojson(db, basin=basin, year=year, metric=metric)


@router.get("/compare")
def gis_compare(
    state: str | None = Query(default=None),
    district: str | None = Query(default=None),
    village: str | None = Query(default=None),
    year_a: int | None = Query(default=None),
    year_b: int | None = Query(default=None),
    metric: str = Query(default="stage"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return service.build_compare(
        db,
        state=state,
        district=district,
        village=village,
        year_a=year_a,
        year_b=year_b,
        metric=metric,
    )


@router.get("/compare/india")
def gis_compare_india(
    year_a: int | None = Query(default=None),
    year_b: int | None = Query(default=None),
    metric: str = Query(default="stage"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return service.build_india_compare(db, year_a=year_a, year_b=year_b, metric=metric)


@router.get("/meta")
def gis_meta(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    meta = service.build_geojson(db)["meta"]
    return {
        "metrics": list(service.METRICS),
        "years": meta["years"],
        "states": meta["states"],
    }