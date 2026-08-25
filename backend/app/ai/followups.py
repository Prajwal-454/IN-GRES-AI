"""Follow-up question suggestions for assistant answers.

After each data/forecast/scenario/terminology answer the assistant proposes up
to three natural next questions derived from the resolved scope, metric and
intent. Suggestions are deterministic — no LLM call — so they stay instant and
never invent data. The frontend renders them as clickable chips that send the
question through the normal message flow.
"""

from __future__ import annotations

from app.ai.assistant import _village_scope

_MAX_SUGGESTIONS = 3


def build_followups(
    state: str | None,
    district: str | None,
    village: str | None,
    metric: str | None,
    intent: str | None,
) -> list[str]:
    """Contextual follow-up questions for an assistant answer."""
    scope = _scope_phrase(state, district, village)
    metric = metric or "stage"

    suggestions: list[str] = []
    if intent in ("data_query", "fallback", "help"):
        if scope:
            suggestions.append(f"What is the forecast for {metric_label(metric)} in {scope}?")
            if district or village:
                suggestions.append(
                    f"Which districts in {state} are over-exploited?"
                    if state
                    else "Which districts are over-exploited?"
                )
            else:
                suggestions.append(f"Which districts are over-exploited in {state}?")
            suggestions.append(f"What if pumping increases 10% in {scope}?")
        else:
            suggestions.append("What is the groundwater status of Telangana?")
            suggestions.append("Which districts are over-exploited in Punjab?")
            suggestions.append("What is an aquifer?")
    elif intent == "forecast":
        if scope:
            suggestions.append(f"What if pumping increases 10% in {scope}?")
            suggestions.append(f"What if recharge decreases 20% in {scope}?")
        suggestions.append("What measures can reduce groundwater extraction?")
    elif intent == "scenario":
        if scope:
            suggestions.append(f"What is the current stage of extraction in {scope}?")
            suggestions.append(f"What is the predicted trend in {scope} next 5 years?")
        suggestions.append("What measures can reduce groundwater extraction?")
    elif intent == "recommend":
        if scope:
            suggestions.append(f"Why is groundwater declining in {scope}?")
            suggestions.append(f"What is the forecast for {scope}?")
        suggestions.append("What measures can reduce groundwater extraction?")
    elif intent == "terminology":
        suggestions.append("What is stage of extraction?")
        suggestions.append("What is the groundwater status of Telangana?")
        suggestions.append("What measures can reduce groundwater extraction?")

    # De-duplicate while preserving order, cap at three.
    seen: set[str] = set()
    unique: list[str] = []
    for s in suggestions:
        key = s.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(s.strip())
    return unique[:_MAX_SUGGESTIONS]


def _scope_phrase(
    state: str | None, district: str | None, village: str | None
) -> str | None:
    if village:
        parts = [_village_scope(village)]
        if district:
            parts.append(district)
        if state:
            parts.append(state)
        return ", ".join(parts)
    if district and state:
        return f"{district} district"
    if district:
        return f"{district} district"
    return state


def metric_label(metric: str) -> str:
    return {
        "stage": "stage of extraction",
        "recharge": "recharge",
        "extraction": "extraction",
        "resource": "extractable resource",
        "rainfall": "rainfall",
        "level": "water level",
    }.get(metric, metric.replace("_", " "))
