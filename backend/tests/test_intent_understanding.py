"""Question-understanding: how-it-works questions must not hit the data engine."""

from app.ai.assistant import classify_intent


def test_how_measured_is_explanation_not_data():
    assert (
        classify_intent("How does the water level is measured?") == "terminology"
    )
    assert classify_intent("How is stage of extraction calculated?") == "terminology"
    assert (
        classify_intent("How is the stage of extraction computed?") == "terminology"
    )


def test_explain_process_questions_are_terminology():
    assert classify_intent("Explain how rainfall data is collected") == "terminology"
    assert classify_intent("How do they estimate recharge?") == "terminology"


def test_value_questions_stay_data_queries():
    assert classify_intent("What is the recharge in Telangana?") == "data_query"
    assert classify_intent("How much recharge in Telangana?") == "data_query"
    assert classify_intent("How many districts are over-exploited?") == "data_query"
    assert classify_intent("Recharge in Guntur district") == "data_query"
    assert (
        classify_intent("Which districts are over-exploited in Punjab?")
        == "data_query"
    )


def test_other_intents_unchanged():
    assert classify_intent("Why is groundwater declining in Punjab?") == "data_query"
    assert classify_intent("How can I reduce groundwater extraction?") == "recommend"
    assert classify_intent("What is an aquifer?") == "terminology"
