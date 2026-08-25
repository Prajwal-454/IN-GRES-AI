"""Superlative / ranking questions ("which state has the lowest recharge")."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.assistant import answer, parse_superlative
from app.database import Base
from app.models.groundwater import (
    AssessmentUnit,
    District,
    GroundwaterAssessment,
    State,
    Village,
)


@pytest.fixture()
def rank_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestingSession()
    # Two states with clearly different recharge totals.
    ap = State(name="Andhra Pradesh", code="AP", region="South")
    sk = State(name="Sikkim", code="SK", region="North East")
    db.add_all([ap, sk])
    db.flush()
    d_ap = District(state_id=ap.id, name="Guntur")
    d_sk = District(state_id=sk.id, name="Gangtok")
    db.add_all([d_ap, d_sk])
    db.flush()
    v_ap = Village(district_id=d_ap.id, name="Randi", is_demo=False)
    v_sk = Village(district_id=d_sk.id, name="Luing", is_demo=False)
    db.add_all([v_ap, v_sk])
    db.flush()
    u_ap = AssessmentUnit(state_id=ap.id, district_id=d_ap.id, village_id=v_ap.id,
                          name="AP unit", is_demo=False)
    u_sk = AssessmentUnit(state_id=sk.id, district_id=d_sk.id, village_id=v_sk.id,
                          name="SK unit", is_demo=False)
    db.add_all([u_ap, u_sk])
    db.flush()
    # Sikkim: tiny recharge; AP: large.
    db.add_all([
        GroundwaterAssessment(assessment_unit_id=u_sk.id, assessment_year=2025,
                              recharge_total=50, extraction_total=10,
                              annual_extractable_resource=40,
                              stage_of_extraction=25, category="Safe", is_demo=False),
        GroundwaterAssessment(assessment_unit_id=u_ap.id, assessment_year=2025,
                              recharge_total=500000, extraction_total=300000,
                              annual_extractable_resource=400000,
                              stage_of_extraction=75, category="Semi-critical",
                              is_demo=False),
        # A demo row that must NOT win (real rows are preferred).
        GroundwaterAssessment(assessment_unit_id=u_sk.id, assessment_year=2025,
                              recharge_total=99999999, extraction_total=1,
                              annual_extractable_resource=99999999,
                              stage_of_extraction=1, category="Safe", is_demo=True),
    ])
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_parse_superlative_variants():
    assert parse_superlative("Which state has the lowest recharge?") == ("min", 1)
    assert parse_superlative("top 5 districts by extraction") == ("max", 5)
    assert parse_superlative("highest stage of extraction") == ("max", 1)
    assert parse_superlative("show the three states with least recharge") == ("min", 3)
    assert parse_superlative("what is recharge in Telangana") is None


def test_lowest_recharge_state(rank_db):
    res = answer("Which state has the lowest recharge?", rank_db, "en")
    assert "Sikkim" in res.content
    assert "lowest" in res.content.lower()
    assert "50.0" in res.content
    assert res.is_demo is False


def test_top_districts_by_extraction_in_state(rank_db):
    res = answer(
        "top districts by extraction in Andhra Pradesh", rank_db, "en"
    )
    assert "Guntur" in res.content
    assert "highest" in res.content.lower() or "extraction" in res.content.lower()


def test_superlative_ignores_demo_rows(rank_db):
    res = answer("state with highest recharge", rank_db, "en")
    assert "Andhra Pradesh" in res.content


def test_top_keyword_does_not_match_top_village(rank_db):
    """'top 3 states…' must rank states, not resolve to a place called Top."""
    res = answer("top 3 states by extraction", rank_db, "en")
    assert "states & UTs" in res.content
    assert "Andhra Pradesh" in res.content


def test_paraphrased_rankings(rank_db):
    cases = [
        ("sabse zyada recharge wala state", "Andhra Pradesh"),
        ("recharge sabse kam kis state mein hai", "Sikkim"),
        ("which state ranks first in pumping", "Andhra Pradesh"),
        ("least recharge state", "Sikkim"),
    ]
    for q, expect in cases:
        res = answer(q, rank_db, "en")
        assert expect in res.content, f"{q!r} -> {res.content[:120]}"


def test_metric_alias_paraphrases():
    from app.ai.assistant import extract_metric

    assert extract_metric("groundwater abstraction in Maharashtra") == "extraction"
    assert extract_metric("pumping in Punjab") == "extraction"
    assert extract_metric("safe yield of Telangana") == "resource"
    assert extract_metric("stage of exploitation in Bihar") == "stage"
    assert extract_metric("rainfall recharge in Kerala") == "recharge"
