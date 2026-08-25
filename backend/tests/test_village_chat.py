"""Tests for village-level chat queries (extraction + data answers)."""

from app.ai.assistant import _extract_location, answer
from app.ai.orchestrator import run


def test_village_extracted_from_district_named_village(client, db_session_factory):
    db = db_session_factory()
    try:
        state, district, village, display = _extract_location(
            db, "What is the stage of extraction in Guntur Village?"
        )
        assert state == "Andhra Pradesh"
        assert district == "Guntur"
        assert village == "Guntur Village"
        assert "Guntur Village" in display
    finally:
        db.close()


def test_bare_district_stays_district_not_village(client, db_session_factory):
    db = db_session_factory()
    try:
        state, district, village, display = _extract_location(
            db, "Recharge in Guntur"
        )
        assert state == "Andhra Pradesh"
        assert district == "Guntur"
        assert village is None
        assert display == "Guntur, Andhra Pradesh"
    finally:
        db.close()


def test_compound_village_not_mistaken_for_district(client, db_session_factory):
    db = db_session_factory()
    try:
        # The demo dataset also has "Guntur Village"; make sure a district that
        # is a substring of a village name is not picked up.
        state, district, village, display = _extract_location(
            db, "What about the extraction in Warangal Village?"
        )
        assert state == "Telangana"
        assert district == "Warangal"
        assert village == "Warangal Village"
    finally:
        db.close()


def test_village_data_answer_single_unit(client, db_session_factory):
    db = db_session_factory()
    try:
        res = answer("Recharge in Guntur Village", db)
        assert res.location == "Guntur Village, Guntur, Andhra Pradesh"
        assert "Guntur Village" in res.content
        assert "assessment units" not in res.content
        assert res.is_demo is True
    finally:
        db.close()


def test_village_stage_answer_includes_category(client, db_session_factory):
    db = db_session_factory()
    try:
        res = answer("What is the stage of extraction in Guntur Village?", db)
        assert "Guntur Village" in res.content
        assert "Assessment category:" in res.content
    finally:
        db.close()


def test_orchestrator_carries_village_over_turns(client, db_session_factory):
    db = db_session_factory()
    try:
        first = run(db, "What is the stage of extraction in Guntur Village?")
        assert first.result.location == "Guntur Village, Guntur, Andhra Pradesh"
        history = [{"role": "user", "content": first.result.content, "location": first.result.location}]
        second = run(db, "And what about the recharge there?", history=history)
        assert second.result.location == "Guntur Village, Guntur, Andhra Pradesh"
        assert "Guntur Village" in second.result.content
    finally:
        db.close()


def test_telugu_state_and_district_extraction(client, db_session_factory):
    db = db_session_factory()
    try:
        state, district, village, display = _extract_location(
            db, "తెలంగాణలో భూగర్భ జల వెలికితీత దశ ఎంత?"
        )
        assert state == "Telangana"
        assert "Telangana" in display
    finally:
        db.close()


def test_telugu_district_extraction(client, db_session_factory):
    db = db_session_factory()
    try:
        state, district, village, display = _extract_location(
            db, "ఆంధ్రప్రదేశ్లో Guntur జిల్లా పునర్భరణం ఎంత?"
        )
        assert state == "Andhra Pradesh"
        assert district == "Guntur"
    finally:
        db.close()


def test_hindi_state_extraction(client, db_session_factory):
    db = db_session_factory()
    try:
        state, district, village, display = _extract_location(
            db, "तेलंगाना में भूजल निष्कर्षण कितना है?"
        )
        assert state == "Telangana"
    finally:
        db.close()


def test_tamil_state_extraction(client, db_session_factory):
    db = db_session_factory()
    try:
        # Tamil Nadu is not in the small demo seed, so the alias must resolve
        # to None rather than raising or matching a wrong state.
        state, district, village, display = _extract_location(
            db, "தமிழ்நாட்டில் நிலத்தடி நீர் நிலை எப்படி?"
        )
        assert state is None
        assert district is None
    finally:
        db.close()


def test_telugu_answer_detects_language(client, db_session_factory):
    db = db_session_factory()
    try:
        res = answer("తెలంగాణలో వెలికితీత దశ ఎంత?", db)
        assert res.language == "te"
        assert res.intent == "data_query"
        assert res.location == "Telangana"
        assert "%" in res.content
    finally:
        db.close()


def test_tamil_answer_language_detected(client, db_session_factory):
    db = db_session_factory()
    try:
        # Data is absent for Tamil Nadu in the demo seed; verify language and
        # intent classification still work for a Tamil data query.
        res = answer("தமிழ்நாட்டில் பிரித்தெடுப்பு நிலை என்ன?", db)
        assert res.language == "ta"
        assert res.intent == "data_query"
    finally:
        db.close()
