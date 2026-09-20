"""LangGraph-style conversational orchestrator.

Implements a small state-graph runtime (nodes + conditional edges + typed state)
mirroring the LangGraph StateGraph pattern. It routes a user message through
language detection, intent classification, entity extraction, and then to the
appropriate agent node:

    START -> detect_language -> classify_intent -> extract_entities -> route
        route -> respond       (greeting / thanks / help)
        route -> data          (structured groundwater query)
        route -> terminology   (term dictionary, RAG/LLM-enriched if needed)
        route -> rag           (knowledge retrieval for free-form questions)
        rag/terminology -> llm (optional LLM answer, falls back to heuristic)

Data answers ALWAYS come from the structured query engine so numbers are never
hallucinated; the LLM (when enabled) is only used for conversational and
knowledge answers.

The runtime is intentionally dependency-free so it can be replaced with the real
`langgraph` package later without changing the node implementations.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai.assistant import AnswerResult, _localise, answer
from app.config import get_settings
from app.rag.llm import compose_answer, generate as llm_generate
from app.rag.llm import generate_search as llm_generate_search
from app.rag.retriever import search as rag_search

logger = logging.getLogger(__name__)

TERMINAL = "__end__"

# Phrases the structured engine uses when the dataset cannot answer the
# question (unknown scope, empty scope, missing year, ...). When one of these
# shows up in a data answer we fall back to web search + LLM instead of
# dead-ending with "no data".
NO_DATA_MARKERS = (
    "I could not find",
    "no groundwater assessment data",
    "not present in the current dataset",
    "don't have",
    "do not have",
)


def _looks_like_no_data(content: str) -> bool:
    low = content.lower()
    return any(marker.lower() in low for marker in NO_DATA_MARKERS)


# Vague place references that must not silently fall back to an all-India answer.
_PLACE_PRONOUNS = (
    "there",
    "here",
    "this area",
    "that area",
    "this district",
    "that district",
    "this village",
    "that village",
    "this place",
    "that place",
    "the above location",
)

_COMPARISON_TRIGGER = re.compile(r"\b(compare|difference between)\b", re.IGNORECASE)


def _comparison_parts(text: str) -> list[str] | None:
    """Two location phrases from 'compare A and B' questions, else None."""
    m = _COMPARISON_TRIGGER.search(text)
    if not m:
        return None
    rest = text[m.end():]
    parts = re.split(
        r"\s+(?:vs\.?|versus|and|with)\s+", rest, maxsplit=1, flags=re.IGNORECASE
    )
    if len(parts) != 2:
        return None
    left = re.sub(r"^(between|of)\s+", "", parts[0].strip(), flags=re.IGNORECASE).strip(" ?.,")
    right = parts[1].strip(" ?.,")
    if not left or not right:
        return None
    return [left, right]


def _needs_location_clarification(state: dict) -> bool:
    """A data question about a place that context could not resolve."""
    if state.get("state_name") or state.get("district") or state.get("village"):
        return False
    text = (state.get("text") or "").lower()
    # Explicitly national/global phrasings are fine without a location.
    if re.search(r"\b(India|all India|nationally|country)\b", text, re.IGNORECASE):
        return False
    return any(p in text for p in _PLACE_PRONOUNS)


def _whether_direction_word(text: str) -> str | None:
    m = re.search(
        r"\b(declining|falling|dropping|decreasing|depleting|rising|increasing"
        r"|improving|recovering|going down|going up)\b",
        text,
        re.IGNORECASE,
    )
    return m.group(1).lower() if m else None


_DOWN_WORDS = {"declining", "falling", "dropping", "decreasing", "depleting", "going down"}


def _with_verdict(state: dict, db: Session, res: "AnswerResult") -> "AnswerResult":
    """Prefix WHETHER-questions with a Yes/No derived from the real series."""
    word = _whether_direction_word(state.get("text") or "")
    if not word or res.response_type != "data" or not res.content:
        return res
    if re.match(r"^\s*(yes|no)\b", res.content, re.IGNORECASE):
        return res  # already leads with a verdict
    try:
        from app.ai.assistant import extract_metric
        from app.ingres import predict

        metric = state.get("metric") or extract_metric(state["text"]) or "stage"
        series = predict.get_scope_series(
            db,
            state.get("state_name"),
            state.get("district"),
            state.get("village"),
            metric if metric in ("stage", "recharge", "extraction") else "stage",
        )
    except Exception:  # noqa: BLE001 - never break the answer over a verdict
        return res
    if len(series) < 2:
        return res
    rising = series[-1]["value"] > series[0]["value"]
    asked_down = word in _DOWN_WORDS
    verdict = "Yes" if rising == asked_down else "No"
    return AnswerResult(
        content=f"{verdict} — {res.content}",
        response_type=res.response_type,
        intent=res.intent,
        language=res.language,
        location=res.location,
        sources=res.sources,
        is_demo=res.is_demo,
    )


class GraphNode:
    def __init__(
        self,
        name: str,
        fn: Callable[[dict, Session], str | None],
        route: Callable[[dict], str] | None = None,
    ):
        self.name = name
        self.fn = fn
        self.route = route

    def __call__(self, state: dict, db: Session) -> str | None:
        return self.fn(state, db)


class StateGraph:
    """Tiny LangGraph-compatible runtime: nodes + conditional edges."""

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.entry: str | None = None

    def add_node(self, name: str, fn: Callable, route: Callable | None = None):
        self.nodes[name] = GraphNode(name, fn, route)
        if self.entry is None:
            self.entry = name

    def set_entry(self, name: str):
        self.entry = name

    def invoke(self, state: dict, db: Session, max_steps: int = 12) -> dict:
        current = self.entry
        for _ in range(max_steps):
            if current is None:
                break
            node = self.nodes[current]
            state["trace"].append(node.name)
            nxt = node(state, db)
            if nxt is None and node.route:
                nxt = node.route(state)
            if nxt is None or nxt == TERMINAL:
                break
            if nxt not in self.nodes:
                logger.error("orchestrator: unknown node %r", nxt)
                break
            current = nxt
        return state


def _llm_enabled() -> bool:
    return bool(get_settings().LLM_ENABLED)


def _build_graph() -> StateGraph:
    g = StateGraph()

    def node_detect_language(state: dict, db: Session) -> str:
        from app.ai.assistant import detect_language

        state["language"] = state.get("language") or detect_language(state["text"])
        return "classify_intent"

    def node_classify_intent(state: dict, db: Session) -> str:
        from app.ai.assistant import classify_intent

        state["intent"] = classify_intent(state["text"])
        return "extract_entities"

    def node_extract_entities(state: dict, db: Session) -> str:
        from app.ai.assistant import _extract_location, extract_metric, extract_year

        text = state["text"]
        state["metric"] = extract_metric(text)
        state["year"] = extract_year(text)
        state_name, district, village, display = _extract_location(db, text)

        # Multi-turn memory: carry over the last known location and metric when
        # the current turn does not mention them explicitly. Follow-ups like
        # "and what about Hyderabad?" keep the previous context.
        if state_name is None or state["metric"] is None:
            for item in reversed(state.get("history") or []):
                content = item.get("content") or ""
                if not content:
                    continue
                if state_name is None and item.get("location"):
                    s, d, v, disp = _extract_location(db, item["location"])
                    if s:
                        state_name, district, village, display = s, d, v, disp
                if state["metric"] is None:
                    m = extract_metric(content)
                    if m:
                        state["metric"] = m
                if state_name is not None and state["metric"] is not None:
                    break

        state["state_name"] = state_name
        state["district"] = district
        state["village"] = village
        state["location_display"] = display
        return "route"

    def route(state: dict) -> str:
        # Comparison questions get a dedicated handler ("compare A and B").
        if _comparison_parts(state["text"]):
            return "compare"
        intent = state["intent"]
        if intent in ("greeting", "thanks", "help"):
            return "respond"
        if intent in ("forecast", "scenario", "recommend"):
            return "data"
        if intent == "data_query":
            if _needs_location_clarification(state):
                return "clarify"
            return "data"
        if intent == "terminology":
            # "what is <metric> in <place>" is really a data query
            if state.get("state_name") and state.get("metric"):
                return "data"
            return "terminology"
        # fallback intents that carried context from earlier turns are data queries
        if state.get("state_name") and state.get("metric"):
            if _needs_location_clarification(state):
                return "clarify"
            return "data"
        if _needs_location_clarification(state):
            return "clarify"
        return "rag"

    _CLARIFY_MESSAGE = (
        "I want to make sure I analyse the right place. Which location would you "
        "like me to look at? Please mention a state, district or village."
    )

    def node_clarify(state: dict, db: Session) -> None:
        state["result"] = AnswerResult(
            content=_CLARIFY_MESSAGE,
            response_type="clarify",
            intent=state.get("intent") or "data_query",
            language=state.get("language") or "en",
        )
        return None

    def _full_control(state: dict, res: AnswerResult) -> AnswerResult:
        """LLM_FULL_CONTROL: the model composes the final reply from the
        verified facts inside ``res``; numbers stay grounded, phrasing is the
        model's. Falls back to the template answer if the LLM is unavailable."""
        settings = get_settings()
        if not settings.LLM_FULL_CONTROL or not settings.LLM_ENABLED:
            return res
        composed = compose_answer(
            state["text"],
            state.get("language") or "en",
            res.content,
            history=state.get("history"),
        )
        if not composed:
            return res
        return AnswerResult(
            content=composed,
            response_type=res.response_type,
            intent=res.intent,
            language=res.language or state.get("language") or "en",
            location=res.location,
            sources=res.sources,
            is_demo=res.is_demo,
        )

    def node_respond(state: dict, db: Session) -> None:
        state["result"] = _full_control(
            state, answer(state["text"], db, state["language"], context=state)
        )
        return None

    def node_data(state: dict, db: Session) -> None:
        res = answer(state["text"], db, state["language"], context=state)
        # WHETHER-questions ("Is the stage rising in Telangana?") must start
        # with a direct Yes/No verdict derived from the actual series.
        res = _with_verdict(state, db, res)
        # Dataset miss: try the internet (and the model's own knowledge)
        # instead of replying "no data" for a question we cannot answer.
        if _looks_like_no_data(res.content):
            fallback = _web_fallback_answer(state, db)
            if fallback is not None:
                state["result"] = fallback
                return None
        state["result"] = _full_control(state, res)
        return None

    def node_compare(state: dict, db: Session) -> str | None:
        from app.ai.assistant import _extract_location

        parts = _comparison_parts(state["text"]) or []
        scopes: list[tuple[str | None, str | None, str | None]] = []
        for side in parts:
            s, d, v, _disp = _extract_location(db, side)
            if s or d or v:
                scopes.append((s or d or v, d if s else None, v))
        if len(scopes) < 2:
            # Unresolved sides -> let RAG/web handle the general comparison.
            state["rag_chunks"] = []
            return "rag"
        from app.ai.assistant import _category_label
        from app.ingres import queries

        rows = []
        for s, d, v in scopes[:2]:
            summ = queries.get_summary(db, state=s, district=d, village=v)
            stage = summ.get("average_stage_of_extraction")
            rows.append(
                {
                    "label": v or (f"{d} district" if d else s) or "—",
                    "recharge": summ.get("total_recharge"),
                    "extraction": summ.get("total_extraction"),
                    "stage": stage,
                    "category": _category_label(stage) if stage else None,
                    "units": summ.get("assessment_units"),
                }
            )
        a, b = rows[0], rows[1]

        def cell(v: float | int | None, suffix: str = "") -> str:
            return f"{v:,.1f}{suffix}" if isinstance(v, (int, float)) else "—"

        content = (
            f"| Indicator | {a['label']} | {b['label']} |\n"
            f"| --- | ---: | ---: |\n"
            f"| Recharge (hm³) | {cell(a['recharge'])} | {cell(b['recharge'])} |\n"
            f"| Extraction (hm³) | {cell(a['extraction'])} | {cell(b['extraction'])} |\n"
            f"| Stage of extraction | {cell(a['stage'], '%')} | {cell(b['stage'], '%')} |\n"
            f"| Category | {a['category'] or '—'} | {b['category'] or '—'} |\n"
            f"| Assessment units | {cell(a['units'], '')} | {cell(b['units'], '')} |"
        )
        try:
            if a["stage"] is not None and b["stage"] is not None:
                better, worse = (a, b) if a["stage"] < b["stage"] else (b, a)
                content += (
                    f"\n\n**{better['label']}** is in better shape: its average "
                    f"stage of extraction ({better['stage']:.1f}%) is lower than "
                    f"{worse['label']}'s ({worse['stage']:.1f}%). Lower stage means "
                    f"less pressure on the aquifer."
                )
        except (TypeError, ValueError):
            pass
        state["result"] = _full_control(
            state,
            AnswerResult(
                content=_localise(content, state.get("language") or "en", source_text=state["text"]),
                response_type="data",
                intent="data_query",
                language=state.get("language") or "en",
                location=f"{a['label']} vs {b['label']}",
                sources=["IN-GRES dataset"],
                is_demo=False,
            ),
        )
        return None

    def _web_fallback_answer(state: dict, db: Session) -> AnswerResult | None:
        """Answer from the internet: prefer a search-native model (Groq
        gpt-oss with browser_search), else DuckDuckGo + the answer model."""
        res = llm_generate_search(
            state["text"], state["language"], history=state.get("history")
        )
        if res is not None:
            state["web_results"] = ["search-model"]
            return res
        web_results = []
        if get_settings().WEB_SEARCH_ENABLED:
            from app.rag.websearch import search as web_search

            state["web_results"] = web_results = web_search(state["text"])
        return llm_generate(
            state["text"],
            state["language"],
            None,
            history=state.get("history"),
            web_results=web_results or None,
        )

    def node_terminology(state: dict, db: Session) -> str | None:
        from app.ai.assistant import DEMO_SOURCE

        res = answer(state["text"], db, state["language"], context=state)
        chunks = rag_search(db, _retrieval_query(state), top_k=3)
        if chunks and "I could not find that term" in res.content:
            state["rag_chunks"] = [c for c, _s in chunks]
            return "llm" if _llm_enabled() else "verbatim"
        if chunks:
            state["result"] = _full_control(
                state,
                AnswerResult(
                    content=_localise(
                        f"{res.content}\n\nMore from the knowledge base:\n{chunks[0]}",
                        res.language,
                        source_text=state["text"],
                    ),
                    response_type="knowledge",
                    intent="terminology",
                    language=res.language,
                    location=res.location,
                    sources=[*res.sources, "IN-GRES AI knowledge base"],
                    is_demo=res.is_demo,
                ),
            )
            return None
        if "I could not find that term" in res.content:
            # Unknown term and no KB hits -> try the web / model knowledge.
            fallback = _web_fallback_answer(state, db)
            if fallback is not None:
                state["result"] = fallback
                return None
        state["result"] = _full_control(state, res)
        return None

    def _retrieval_query(state: dict) -> str:
        """Question + resolved entities so retrieval follows the question."""
        extras = [
            x
            for x in (state.get("state_name"), state.get("district"), state.get("metric"))
            if x
        ]
        return f"{state['text']} {' '.join(extras)}" if extras else state["text"]

    def node_rag(state: dict, db: Session) -> str:
        chunks = rag_search(db, _retrieval_query(state), top_k=3)
        # Drop weak BM25 matches so general-knowledge questions (which only
        # accidentally share a word or two with the groundwater corpus) reach
        # the LLM with clean context — or none at all.
        filtered: list[str] = []
        if chunks:
            best = chunks[0][1]
            floor = max(2.0, best * 0.25)
            filtered = [c for c, s in chunks if s >= floor]
        state["rag_chunks"] = filtered
        return "llm" if _llm_enabled() else "verbatim"

    def node_verbatim(state: dict, db: Session) -> None:
        chunks = state.get("rag_chunks") or []
        if chunks:
            state["result"] = _full_control(
                state,
                AnswerResult(
                    content=_localise(
                        f"Here is what I found in the knowledge base:\n\n{chunks[0]}",
                        state["language"],
                        source_text=state["text"],
                    ),
                    response_type="knowledge",
                    intent=state.get("intent") or "fallback",
                    language=state["language"],
                    sources=["IN-GRES AI knowledge base"],
                    is_demo=False,
                ),
            )
            return None
        state["result"] = _full_control(
            state, answer(state["text"], db, state["language"], context=state)
        )
        return None

    def node_llm(state: dict, db: Session) -> str | None:
        chunks = state.get("rag_chunks") or []
        if not chunks:
            # Internet first: a search-native model (Groq gpt-oss with
            # browser_search) browses itself; otherwise DuckDuckGo + model.
            res = llm_generate_search(
                state["text"], state["language"], history=state.get("history")
            )
            if res is not None:
                state["web_results"] = ["search-model"]
                state["result"] = res
                return None
            web_results = []
            if get_settings().WEB_SEARCH_ENABLED:
                from app.rag.websearch import search as web_search

                state["web_results"] = web_results = web_search(state["text"])
        else:
            web_results = []
        res = llm_generate(
            state["text"],
            state["language"],
            chunks,
            history=state.get("history"),
            web_results=web_results or None,
        )
        if res is not None:
            state["result"] = res
            return None
        return "verbatim" if chunks else "respond_fallback"

    def node_respond_fallback(state: dict, db: Session) -> None:
        state["result"] = answer(state["text"], db, state["language"], context=state)
        return None

    g.add_node("detect_language", node_detect_language)
    g.add_node("classify_intent", node_classify_intent)
    g.add_node("extract_entities", node_extract_entities)
    g.add_node("route", lambda s, db: None, route=route)
    g.add_node("respond", node_respond)
    g.add_node("clarify", node_clarify)
    g.add_node("data", node_data)
    g.add_node("compare", node_compare)
    g.add_node("terminology", node_terminology)
    g.add_node("rag", node_rag)
    g.add_node("verbatim", node_verbatim)
    g.add_node("llm", node_llm)
    g.add_node("respond_fallback", node_respond_fallback)
    g.set_entry("detect_language")
    return g


_graph: StateGraph | None = None


def run(
    db: Session,
    text: str,
    language: str | None = None,
    history: list[dict] | None = None,
) -> "GraphAnswer":
    """Run the orchestrator graph and return a GraphAnswer.

    ``history`` is a list of prior turns as ``{"role", "content", "location"}``
    dicts (oldest first) used for multi-turn context carry-over.
    """
    global _graph
    if _graph is None:
        _graph = _build_graph()

    start = time.perf_counter()
    state: dict[str, Any] = {
        "text": text,
        "language": language,
        "intent": None,
        "metric": None,
        "year": None,
        "state_name": None,
        "district": None,
        "village": None,
        "location_display": None,
        "rag_chunks": [],
        "history": history or [],
        "result": None,
        "trace": [],
    }

    state = _graph.invoke(state, db)

    latency = int((time.perf_counter() - start) * 1000)
    if state.get("result") is None:
        state["result"] = answer(text, db, state.get("language"), context=state)
    return GraphAnswer(
        result=state["result"],
        trace=state["trace"],
        latency_ms=latency,
        context=state,
    )


@dataclass
class GraphAnswer:
    result: AnswerResult
    trace: list[str] = field(default_factory=list)
    latency_ms: int = 0
    context: dict = field(default_factory=dict)