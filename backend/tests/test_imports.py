"""Tests for the dataset import pipeline and import API."""

import csv
import io

from app.ingres.data_import import _normalise_category, import_dataset


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def test_normalise_category():
    assert _normalise_category(" over-exploited ") == "Over-exploited"
    assert _normalise_category("semi-critical") == "Semi-critical"
    assert _normalise_category("Safe") == "Safe"
    assert _normalise_category(None) is None


def test_import_dataset_valid_csv(db_session_factory):
    content = _csv_bytes(
        [
            ["state", "district", "assessment_unit", "year", "recharge", "extraction", "stage", "category"],
            ["Kerala", "Trivandrum", "Trivandrum Block 1", 2021, "120.5", "80", "66.4", "Safe"],
            ["Kerala", "Trivandrum", "Trivandrum Block 2", 2021, "90", "110", "122.2", "Over-exploited"],
        ]
    )
    db = db_session_factory()
    try:
        result = import_dataset(
            db, "kerala.csv", content, user_id=1, name="Kerala 2021", source="Test"
        )
        assert result.errors == []
        assert result.rows_imported == 2
        assert result.dataset_id is not None
        assert "Kerala" in result.states_created
        assert any("Trivandrum Block 1" in u for u in result.units_created)
    finally:
        db.close()


def test_import_dataset_missing_columns(db_session_factory):
    content = _csv_bytes(
        [["name", "value"], ["a", "1"]]
    )
    db = db_session_factory()
    try:
        result = import_dataset(db, "bad.csv", content, user_id=1)
        assert result.dataset_id is None
        assert any("Missing required column" in e for e in result.errors)
    finally:
        db.close()


def test_import_dataset_bad_number_rejected(db_session_factory):
    content = _csv_bytes(
        [
            ["state", "district", "assessment_unit", "year", "recharge"],
            ["Kerala", "Trivandrum", "Trivandrum Block 1", 2021, "not-a-number"],
        ]
    )
    db = db_session_factory()
    try:
        result = import_dataset(db, "badnum.csv", content, user_id=1)
        assert result.dataset_id is None
        assert any("not a number" in e for e in result.errors)
    finally:
        db.close()


def test_import_api_template(client, admin_token, user_token):
    # Only admins can download the template.
    resp = client.get("/api/admin/datasets/import/template", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 403
    resp = client.get("/api/admin/datasets/import/template", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert "state" in resp.content.decode("utf-8")


def test_import_api_upload(client, admin_token):
    content = _csv_bytes(
        [
            ["state", "district", "assessment_unit", "year", "recharge", "extraction", "stage", "category"],
            ["Karnataka", "Bengaluru Urban", "Bengaluru Block 1", 2021, "100", "90", "90.0", "Critical"],
        ]
    )
    resp = client.post(
        "/api/admin/datasets/import",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("karnataka.csv", content, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rows_imported"] == 1
    assert body["dataset_id"] is not None


def test_import_api_rejects_bad_file(client, admin_token):
    resp = client.post(
        "/api/admin/datasets/import",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("bad.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 422
