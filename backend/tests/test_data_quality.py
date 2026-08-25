from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ingres.query_cache import invalidate_analytics_cache
from app.models.groundwater import (
    AssessmentUnit,
    GroundwaterAssessment,
)


def _inject_bad_row(db) -> GroundwaterAssessment:
    """One assessment row with a physically impossible stage value."""
    unit_id = db.scalar(select(AssessmentUnit.id).limit(1))
    row = GroundwaterAssessment(
        assessment_unit_id=unit_id,
        dataset_id=None,
        assessment_year=2099,
        recharge_total=Decimal("100"),
        extraction_total=Decimal("-20"),
        annual_extractable_resource=None,
        stage_of_extraction=Decimal("-5"),
        category="safe",
        is_demo=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_scan_flags_and_review_workflow(client: TestClient, auth_admin, db_session_factory):
    db = db_session_factory()
    row = None
    try:
        row = _inject_bad_row(db)
        before = client.get("/api/quality/summary", headers=auth_admin).json()

        scan = client.post("/api/quality/scan", headers=auth_admin)
        assert scan.status_code == 200, scan.text
        body = scan.json()
        assert body["scanned"] > 0
        assert body["created"] >= 2  # impossible stage + negative extraction

        listing = client.get(
            "/api/quality/flags",
            params={"status": "open"},
            headers=auth_admin,
        )
        assert listing.status_code == 200
        flags = listing.json()["flags"]
        kinds = {f["kind"] for f in flags}
        assert "impossible_value" in kinds
        assert "negative_value" in kinds
        target = next(f for f in flags if f["kind"] == "impossible_value" and f["year"] == 2099)
        assert target["severity"] == "high"
        assert target["value"] == -5.0
        assert target["status"] == "open"

        # Acknowledge, then resolve.
        acked = client.patch(
            f"/api/quality/flags/{target['id']}",
            json={"status": "acknowledged", "review_note": "checking with district office"},
            headers=auth_admin,
        )
        assert acked.status_code == 200, acked.text
        assert acked.json()["status"] == "acknowledged"
        resolved = client.patch(
            f"/api/quality/flags/{target['id']}",
            json={"status": "resolved", "review_note": "typo in source CSV"},
            headers=auth_admin,
        )
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"

        # Re-scanning must not duplicate known fingerprints.
        rescan = client.post("/api/quality/scan", headers=auth_admin)
        assert rescan.status_code == 200
        assert rescan.json()["created"] == 0

        after = client.get("/api/quality/summary", headers=auth_admin).json()
        assert set(after) >= {"total_open", "by_status", "by_severity", "last_scan_at"}
        assert before != after or after["by_status"].get("open", 0) >= 1
    finally:
        # Remove the injected row so other tests keep a clean series.
        if row is not None:
            db.delete(row)
            db.commit()
        from app.models.quality import AnomalyFlag

        for flag in db.scalars(select(AnomalyFlag)).all():
            db.delete(flag)
        db.commit()
        invalidate_analytics_cache()


def test_quality_requires_admin(client: TestClient, auth_user):
    assert client.get("/api/quality/summary", headers=auth_user).status_code == 403
    assert client.get("/api/quality/flags", headers=auth_user).status_code == 403
    assert client.post("/api/quality/scan", headers=auth_user).status_code == 403


def test_flag_review_validation(client: TestClient, auth_admin):
    resp = client.patch(
        "/api/quality/flags/999999",
        json={"status": "resolved"},
        headers=auth_admin,
    )
    assert resp.status_code == 404


def test_flags_filtering(client: TestClient, auth_admin):
    listing = client.get(
        "/api/quality/flags",
        params={"status": "all", "severity": "high"},
        headers=auth_admin,
    )
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == len([f for f in body["flags"]])
