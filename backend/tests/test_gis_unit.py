"""Unit tests for the GIS helper functions (no database needed)."""

from app.gis.service import _square_polygon, centroid_for


def test_square_polygon():
    ring = _square_polygon(17.0, 78.0, size=0.7)
    assert len(ring) == 5  # closed ring
    assert ring[0] == ring[-1]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    assert min(lons) == 78.0 - 0.35
    assert max(lons) == 78.0 + 0.35
    assert min(lats) == 17.0 - 0.35
    assert max(lats) == 17.0 + 0.35


def test_centroid_for_known_districts():
    assert centroid_for("Hyderabad") is not None
    assert centroid_for("Guntur") is not None
    assert centroid_for("Nizamabad") is not None


def test_centroid_for_unknown_returns_none():
    assert centroid_for("Not A District") is None
