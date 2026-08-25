"""AI-generated groundwater assessment report.

Builds a structured report payload (executive summary, status, trend,
prediction, risk, map, recommendations, data sources) for a state/district
and period, then renders it as PDF (reportlab) or Excel (openpyxl).
"""

from __future__ import annotations

import io
import math
from datetime import datetime, timezone

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.shapes import Drawing, Line, Polygon, PolyLine, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.ai.assistant import _category_label, _recommendations_for_stage
from app.gis import service as gis
from app.ingres import predict, queries

DEMO_SOURCE = "Synthetic Development Dataset (demo)"

CATEGORY_COLORS = {
    "safe": "#16a34a",
    "semi-critical": "#eab308",
    "critical": "#f97316",
    "over-exploited": "#dc2626",
}
NO_DATA_COLOR = "#e5e7eb"
RISK_SEVERITY = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
DIRECTION_LABELS = {"rising": "rising", "falling": "declining", "stable": "broadly stable"}


def _category(stage: float | None) -> str | None:
    if stage is None:
        return None
    return _category_label(stage)


def _risk(category: str | None) -> str | None:
    return gis._risk_for_category(category)


def build_assessment_report(
    db,
    state: str | None = None,
    district: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict:
    """Build the full assessment report payload for a scope and period."""
    latest = queries.get_latest_year(db, state=state, district=district)
    if latest is None:
        raise HTTPException(status_code=404, detail="No assessment data for this scope.")
    years = gis.available_years(db)
    if not years:
        raise HTTPException(status_code=404, detail="No assessment data available.")

    start = year_from or min(years)
    start = max(start, min(years))
    if start > latest:
        start = latest
    requested_to = year_to or (latest + 5)
    horizon = max(1, min(int(requested_to) - latest, 10))
    end_year = latest + horizon

    summary = queries.get_summary(db, state=state, district=district, year=latest)
    stage = float(summary.get("average_stage_of_extraction") or 0.0)
    category = _category(stage)
    recharge = float(summary.get("total_recharge") or 0.0)
    extraction = float(summary.get("total_extraction") or 0.0)
    resource = (extraction / (stage / 100.0)) if stage > 0 else None
    water_level = gis.water_level_from_stage(stage)

    series_map = {
        "stage": predict.get_scope_series(db, state, district, None, "stage"),
        "recharge": predict.get_scope_series(db, state, district, None, "recharge"),
        "extraction": predict.get_scope_series(db, state, district, None, "extraction"),
    }
    by_year: dict[int, dict] = {}
    for metric, series in series_map.items():
        for p in series:
            by_year.setdefault(int(p["year"]), {})[metric] = round(float(p["value"]), 2)
    trend_series = [
        {
            "year": y,
            "stage": v.get("stage", 0.0),
            "recharge": v.get("recharge", 0.0),
            "extraction": v.get("extraction", 0.0),
        }
        for y, v in sorted(by_year.items())
        if y >= start
    ]

    fc = predict.forecast(
        db, state=state, district=district, metric="stage", horizon=horizon, method="auto"
    )
    end_value = fc.get("end_value")
    if end_value is None and fc.get("forecast"):
        end_value = fc["forecast"][-1]["value"]
    end_value = round(float(end_value), 2) if end_value is not None else None
    predicted_category = _category(end_value) if end_value is not None else category
    current_risk = _risk(category)
    predicted_risk = _risk(predicted_category)
    candidates = [r for r in (current_risk, predicted_risk) if r]
    level = max(candidates, key=lambda r: RISK_SEVERITY.get(r, 0)) if candidates else "Unknown"

    scope_display = " · ".join(x for x in (state, district) if x) or "All states"
    recommendations = _recommendations_for_stage(stage)[:5]

    if district:
        geo = gis.build_geojson(db, state=state, district=district, year=latest, metric="stage")
    else:
        geo = gis.build_prediction_geojson(
            db, state=state, year=latest, target_year=latest, metric="stage"
        )

    report = {
        "scope": {"state": state, "district": district, "display": scope_display},
        "period": {"from": start, "to": end_year, "requested_to": requested_to, "latest": latest},
        "is_demo": True,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "status": {
            "year": latest,
            "assessment_units": int(summary.get("assessment_units") or 0),
            "recharge": round(recharge, 2),
            "extraction": round(extraction, 2),
            "resource": round(resource, 2) if resource is not None else None,
            "stage": round(stage, 2),
            "category": category,
            "water_level": {
                "value": round(water_level, 2) if water_level is not None else None,
                "unit": "m",
                "trend_per_year": round(fc["slope"] / 10.0, 2) if fc.get("slope") is not None else None,
            },
            "category_counts": summary.get("category_counts", []),
        },
        "trend": {
            "metric": "stage",
            "unit": "%",
            "series": trend_series,
            "direction": fc.get("direction", "stable"),
            "slope": round(float(fc["slope"]), 2) if fc.get("slope") is not None else None,
            "pct_change": round(float(fc["pct_change"]), 1) if fc.get("pct_change") is not None else None,
        },
        "prediction": {
            "metric": "stage",
            "unit": "%",
            "method": fc.get("method"),
            "method_label": fc.get("method_label"),
            "best_method": fc.get("best_method"),
            "direction": fc.get("direction", "stable"),
            "pct_change": round(float(fc["pct_change"]), 1) if fc.get("pct_change") is not None else None,
            "r2": round(float(fc["r2"]), 3) if fc.get("r2") is not None else None,
            "slope": round(float(fc["slope"]), 2) if fc.get("slope") is not None else None,
            "risk": fc.get("risk"),
            "years_to_threshold": fc.get("years_to_threshold"),
            "end_value": end_value,
            "end_year": end_year,
            "historical": fc.get("historical", []),
            "forecast": fc.get("forecast", []),
            "note": fc.get("note", ""),
        },
        "risk": {
            "current": current_risk,
            "predicted": predicted_risk,
            "level": level,
            "current_category": category,
            "predicted_category": predicted_category,
            "summary": _risk_summary(scope_display, current_risk, predicted_risk, level, end_value, end_year, fc.get("years_to_threshold")),
        },
        "map": {
            "type": "FeatureCollection",
            "features": geo.get("features", []),
            "meta": {"metric": "stage", "year": latest, "target_year": end_year},
        },
        "recommendations": recommendations,
        "sources": [
            DEMO_SOURCE,
            "Assessment records: state, district, assessment unit, year, recharge, extraction, annual extractable resource, stage of extraction and category (2017-2022).",
            f"Prediction: linear regression on the yearly stage-of-extraction series with a 95% confidence band (model: {fc.get('method_label', 'auto')}).",
            "Category thresholds: Safe <70%, Semi-critical 70-90%, Critical 90-100%, Over-exploited >=100%.",
            "Water level is derived illustratively (depth in m = 1.2 + stage/100 x 10); the demo dataset has no measured groundwater levels.",
            "Derived by IN-GRES AI from the synthetic development dataset - not official CGWB statistics.",
        ],
    }
    report["executive_summary"] = _executive_summary(report)
    return report


def _executive_summary(r: dict) -> list[str]:
    scope = r["scope"]["display"]
    st = r["status"]
    per = r["period"]
    pr = r["prediction"]
    rs = r["risk"]
    lines = [
        (
            f"{scope} recorded an average stage of extraction of {st['stage']:.1f}% in {per['latest']}, "
            f"classified as {st['category'] or 'Unknown'}, across {st['assessment_units']} assessment units. "
            f"Annual recharge was {st['recharge']:.1f} hm³ and extraction {st['extraction']:.1f} hm³."
        )
    ]
    direction = DIRECTION_LABELS.get(pr["direction"], "broadly stable")
    if pr["slope"] is not None:
        lines.append(
            f"Over {per['from']}-{per['latest']} the stage-of-extraction trend is {direction}, moving by "
            f"{abs(pr['slope']):.1f} points per year."
        )
    if pr["end_value"] is not None:
        lines.append(
            f"Under the current trend, stage is projected to reach {pr['end_value']:.1f}% by {per['to']}, "
            f"shifting the scope from {st['category'] or 'n/a'} to {rs['predicted_category'] or 'n/a'}."
        )
        if pr["years_to_threshold"] is not None:
            lines.append(
                f"The over-exploited threshold (100%) is projected to be crossed in about "
                f"{pr['years_to_threshold']} year(s)."
            )
    if r["recommendations"]:
        lines.append(
            f"Overall risk is assessed as {rs['level']}. Priority actions include "
            f"{r['recommendations'][0].lower()} and {r['recommendations'][1].lower()}."
        )
    return lines


def _risk_summary(scope, current, predicted, level, end_value, end_year, years_to_threshold) -> str:
    parts = [f"{scope} is currently assessed as {level} risk ({current or 'n/a'})."]
    if end_value is not None:
        parts.append(
            f"If the current trend continues, stage is projected to reach {end_value:.1f}% by {end_year} "
            f"({predicted or 'n/a'})."
        )
    if years_to_threshold is not None:
        parts.append(
            f"The 100% over-exploited threshold is projected to be crossed in about "
            f"{years_to_threshold} year(s)."
        )
    else:
        parts.append("The projected trend stays within the current category band over the report horizon.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

def _styled_table(header: list[str], rows: list[list[str]], col_widths=None, font_size=8) -> Table:
    data = [header] + rows
    table = Table(data, colWidths=col_widths)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    table.setStyle(TableStyle(style))
    return table


def _flatten(points: list[tuple[float, float]]) -> list[float]:
    return [coord for pt in points for coord in pt]


def _chart_drawing(points: list[dict], title: str, unit: str = "%", width: int = 520, height: int = 170) -> Drawing:
    pad_l, pad_r, pad_t, pad_b = 42, 18, 30, 26
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    if not points:
        d = Drawing(width, height)
        d.add(String(width / 2, height / 2, "No data", fontSize=9, textAnchor="middle", fillColor=colors.grey))
        return d

    values = [p["value"] for p in points]
    for p in points:
        if p.get("upper") is not None:
            values.append(p["upper"])
        if p.get("lower") is not None:
            values.append(p["lower"])
    lo = min(min(values), 0.0)
    hi = max(max(values), 1.0)
    if unit == "%":
        hi = max(hi, 105)
        lo = min(lo, 0.0)
    span = hi - lo or 1.0

    def X(i: int) -> float:
        return pad_l + (i * plot_w) / max(len(points) - 1, 1)

    def Y(v: float) -> float:
        return pad_t + (1 - (v - lo) / span) * plot_h

    d = Drawing(width, height)
    d.add(Line(pad_l, pad_t, pad_l, pad_t + plot_h, strokeColor=colors.grey, strokeWidth=0.6))
    d.add(Line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, strokeColor=colors.grey, strokeWidth=0.6))
    d.add(Line(pad_l, pad_t, pad_l + plot_w, pad_t, strokeColor=colors.grey, strokeWidth=0.6))
    d.add(Line(pad_l + plot_w, pad_t, pad_l + plot_w, pad_t + plot_h, strokeColor=colors.grey, strokeWidth=0.6))

    for k in range(5):
        v = lo + span * k / 4
        y = Y(v)
        d.add(Line(pad_l, y, pad_l + plot_w, y, strokeColor=colors.Color(0.9, 0.92, 0.95), strokeWidth=0.5))
        d.add(String(pad_l - 5, y - 3, f"{v:.0f}", fontSize=7, textAnchor="end", fillColor=colors.grey))

    step = max(1, len(points) // 10)
    for i, p in enumerate(points):
        if i % step == 0:
            d.add(String(X(i), pad_t + plot_h + 5, str(p["year"]), fontSize=7, textAnchor="middle", fillColor=colors.grey))

    has_band = any(p.get("upper") is not None for p in points)
    if has_band:
        upper = [(X(i), Y(p["upper"])) for i, p in enumerate(points) if p.get("upper") is not None]
        lower_rev = [(X(i), Y(p["lower"])) for i, p in enumerate(points) if p.get("lower") is not None][::-1]
        if upper and lower_rev:
            d.add(Polygon(_flatten(upper + lower_rev), fillColor=colors.HexColor("#bfe3ff"), strokeColor=colors.HexColor("#bfe3ff"), strokeWidth=0.5))

    historical = [p for p in points if p.get("upper") is None]
    forecast = [p for p in points if p.get("upper") is not None]
    if len(historical) > 1:
        d.add(PolyLine(_flatten([(X(i), Y(p["value"])) for i, p in enumerate(points) if p.get("upper") is None]),
                       strokeColor=colors.HexColor("#0f766e"), strokeWidth=1.6))
    if len(forecast) > 1:
        d.add(PolyLine(_flatten([(X(i), Y(p["value"])) for i, p in enumerate(points) if p.get("upper") is not None]),
                       strokeColor=colors.HexColor("#0284c7"), strokeWidth=1.6))

    for i, p in enumerate(points):
        if p.get("upper") is not None:
            y_lo, y_hi = Y(p["lower"]), Y(p["upper"])
            d.add(Line(X(i), y_lo, X(i), y_hi, strokeColor=colors.HexColor("#0284c7"), strokeWidth=1.2))
        d.add(Polygon(_flatten([(X(i) - 1.8, Y(p["value"]) - 1.8), (X(i) + 1.8, Y(p["value"]) - 1.8), (X(i) + 1.8, Y(p["value"]) + 1.8), (X(i) - 1.8, Y(p["value"]) + 1.8)]),
                      fillColor=colors.HexColor("#0f766e") if p.get("upper") is None else colors.HexColor("#0284c7"),
                      strokeColor=None, strokeWidth=0))

    d.add(String(width / 2, height - 12, title, fontSize=9, textAnchor="middle", fillColor=colors.black))
    return d


def _map_drawing(features: list[dict], width: int = 520, height: int = 320, title: str = "Groundwater status map") -> Drawing:
    rings: list[tuple[list[tuple[float, float]], str]] = []
    for f in features:
        g = f.get("geometry") or {}
        category = (f.get("properties") or {}).get("category")
        fill = CATEGORY_COLORS.get(category, NO_DATA_COLOR) if category else NO_DATA_COLOR
        if g.get("type") == "Polygon":
            polys = [g.get("coordinates") or []]
        else:
            polys = g.get("coordinates") or []
        for poly in polys:
            if poly:
                ring = [(pt[0], pt[1]) for pt in poly[0]]
                rings.append((ring, fill))

    d = Drawing(width, height)
    d.add(String(width / 2, height - 12, title, fontSize=9, textAnchor="middle", fillColor=colors.black))
    if not rings:
        d.add(String(width / 2, height / 2, "No map data", fontSize=9, textAnchor="middle", fillColor=colors.grey))
        return d

    lngs = [pt[0] for ring, _ in rings for pt in ring]
    lats = [pt[1] for ring, _ in rings for pt in ring]
    min_lng, max_lng = min(lngs), max(lngs)
    min_lat, max_lat = min(lats), max(lats)
    k = math.cos(math.radians((min_lat + max_lat) / 2))
    span_x = (max_lng - min_lng) * k or 1.0
    span_y = max_lat - min_lat or 1.0
    box_w = width - 16
    box_h = height - 34
    scale = min(box_w / span_x, box_h / span_y)
    cx = (min_lng + max_lng) / 2
    cy = (min_lat + max_lat) / 2

    def proj(lng: float, lat: float) -> tuple[float, float]:
        x = width / 2 + (lng - cx) * k * scale
        y = height / 2 + (cy - lat) * scale
        return x, y

    for ring, fill in rings:
        pts = [proj(lng, lat) for lng, lat in ring]
        d.add(Polygon(_flatten(pts), fillColor=colors.HexColor(fill), strokeColor=colors.white, strokeWidth=0.6))
    return d


def render_assessment_pdf(report: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="IN-GRES AI Groundwater Assessment Report",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=9.5, leading=13, spaceAfter=4)
    h1 = ParagraphStyle(name="H1", parent=styles["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=5)
    small = ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)

    story: list = []
    story.append(Paragraph("IN-GRES AI — Groundwater Assessment Report", styles["Title"]))
    story.append(Paragraph("Indian Groundwater Resource Estimation System", styles["Normal"]))
    story.append(Paragraph(f"Scope: <b>{report['scope']['display']}</b> · Period {report['period']['from']}–{report['period']['to']} (latest data {report['period']['latest']})", body))
    story.append(Paragraph(f"Generated {report['generated_at']}", small))
    if report["is_demo"]:
        story.append(Paragraph(
            "⚠️ Report generated from the synthetic development dataset — demo data, not official statistics.",
            ParagraphStyle(name="Demo", parent=body, textColor=colors.HexColor("#b45309")),
        ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("1. Executive Summary", h1))
    for line in report["executive_summary"]:
        story.append(Paragraph(line, body))

    story.append(Paragraph("2. Groundwater Status", h1))
    st = report["status"]
    status_rows = [
        ["Assessment units", str(st["assessment_units"]), ""],
        ["Annual recharge", f"{st['recharge']:,.1f}", "hm³"],
        ["Annual extraction", f"{st['extraction']:,.1f}", "hm³"],
        ["Annual extractable resource", f"{st['resource']:,.1f}" if st["resource"] is not None else "-", "hm³"],
        ["Average stage of extraction", f"{st['stage']:.1f}", "%"],
        ["Category", st["category"] or "-", ""],
        ["Derived water level", f"{st['water_level']['value']:.1f}" if st["water_level"]["value"] is not None else "-", "m"],
    ]
    story.append(_styled_table(["Metric", "Value", "Unit"], status_rows, col_widths=[70 * mm, 45 * mm, 25 * mm]))
    story.append(Spacer(1, 3 * mm))
    if st["category_counts"]:
        story.append(Paragraph("Category distribution", ParagraphStyle(name="H2", parent=body, fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=3)))
        story.append(_styled_table(
            ["Category", "Units"],
            [[c["category"], str(c["count"])] for c in st["category_counts"]],
            col_widths=[80 * mm, 40 * mm],
        ))

    story.append(Paragraph("3. Historical Trend", h1))
    tr = report["trend"]
    if tr["slope"] is not None:
        story.append(Paragraph(
            f"Trend {DIRECTION_LABELS.get(tr['direction'], 'broadly stable')} at {abs(tr['slope']):.1f} points/year "
            f"({tr['pct_change']:+}% projected change).",
            body,
        ))
    chart_points = [{"year": s["year"], "value": s["stage"]} for s in tr["series"]]
    story.append(_chart_drawing(chart_points, "Stage of extraction (%)", unit="%"))
    story.append(Spacer(1, 3 * mm))
    trend_rows = [["Year", "Stage %", "Recharge (hm³)", "Extraction (hm³)"]]
    for s in tr["series"]:
        trend_rows.append([str(s["year"]), f"{s['stage']:.1f}", f"{s['recharge']:,.1f}", f"{s['extraction']:,.1f}"])
    story.append(_styled_table(trend_rows[0], trend_rows[1:], col_widths=[22 * mm, 28 * mm, 45 * mm, 45 * mm]))

    story.append(Paragraph("4. Prediction", h1))
    pr = report["prediction"]
    meta_rows = [
        ["Model", (pr.get("method_label") or "auto") + (f" ({pr.get('best_method')})" if pr.get("best_method") else "")],
        ["Direction", DIRECTION_LABELS.get(pr["direction"], "stable")],
        ["R²", f"{pr['r2']:.3f}" if pr["r2"] is not None else "-"],
        ["Projected change", f"{pr['pct_change']:+}%" if pr["pct_change"] is not None else "-"],
        [f"Stage at {pr['end_year']}", f"{pr['end_value']:.1f}%" if pr["end_value"] is not None else "-"],
        ["Years to over-exploited threshold", str(pr["years_to_threshold"]) if pr["years_to_threshold"] is not None else "n/a"],
    ]
    story.append(_styled_table(["Property", "Value"], meta_rows, col_widths=[75 * mm, 65 * mm]))
    story.append(Spacer(1, 3 * mm))
    pred_points = [{"year": p["year"], "value": p["value"]} for p in pr["historical"] if p["year"] >= report["period"]["from"]] + list(pr["forecast"])
    story.append(_chart_drawing(pred_points, f"Stage of extraction — projection to {pr['end_year']} (%)", unit="%"))
    story.append(Spacer(1, 3 * mm))
    pred_rows = [["Year", "Stage %", "Lower", "Upper"]]
    for p in pred_points:
        pred_rows.append([
            str(p["year"]),
            f"{p['value']:.1f}",
            f"{p['lower']:.1f}" if p.get("lower") is not None else "-",
            f"{p['upper']:.1f}" if p.get("upper") is not None else "-",
        ])
    story.append(_styled_table(pred_rows[0], pred_rows[1:], col_widths=[22 * mm, 30 * mm, 40 * mm, 40 * mm]))

    story.append(Paragraph("5. Risk Analysis", h1))
    rs = report["risk"]
    story.append(Paragraph(rs["summary"], body))
    story.append(Spacer(1, 2 * mm))
    story.append(_styled_table(
        ["Item", "Current", "Projected"],
        [
            ["Category", rs["current_category"] or "-", rs["predicted_category"] or "-"],
            ["Risk level", rs["current"] or "-", rs["predicted"] or "-"],
        ],
        col_widths=[45 * mm, 45 * mm, 45 * mm],
    ))

    story.append(Paragraph("6. Map", h1))
    story.append(_map_drawing(report["map"]["features"], title=f"{report['scope']['display']} — status {report['map']['meta']['year']}"))

    story.append(Paragraph("7. Recommendations", h1))
    rec_items = [ListItem(Paragraph(f"• {r}", body)) for r in report["recommendations"]]
    story.append(ListFlowable(rec_items, bulletType="bullet", start="•", leftIndent=12))

    story.append(Paragraph("8. Data Sources", h1))
    for s in report["sources"]:
        story.append(Paragraph(f"• {s}", body))

    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Excel rendering
# ---------------------------------------------------------------------------

def render_assessment_xlsx(report: dict) -> bytes:
    wb = Workbook()
    header_fill = PatternFill("solid", fgColor="0F766E")
    header_font = Font(bold=True, color="FFFFFF")
    bold = Font(bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")

    def sheet_with_header(name: str, titles: list[str]):
        ws = wb.create_sheet(name)
        for c, t in enumerate(titles, 1):
            cell = ws.cell(row=1, column=c, value=t)
            cell.fill = header_fill
            cell.font = header_font
        return ws

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Groundwater Assessment Report"
    ws["A1"].font = Font(bold=True, size=14)
    meta = [
        ("Scope", report["scope"]["display"]),
        ("Period", f"{report['period']['from']}-{report['period']['to']}"),
        ("Latest data", str(report["period"]["latest"])),
        ("Generated", report["generated_at"]),
        ("Source", report["sources"][0]),
    ]
    for i, (k, v) in enumerate(meta, 3):
        ws.cell(row=i, column=1, value=k).font = bold
        ws.cell(row=i, column=2, value=v)
    start = 3 + len(meta) + 1
    ws.cell(row=start, column=1, value="Executive Summary").font = Font(bold=True, size=12)
    for i, line in enumerate(report["executive_summary"], start + 1):
        ws.cell(row=i, column=1, value=line).alignment = wrap
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 60

    ws = sheet_with_header("Status", ["Metric", "Value", "Unit"])
    st = report["status"]
    status_rows = [
        ["Assessment units", st["assessment_units"], ""],
        ["Annual recharge", st["recharge"], "hm³"],
        ["Annual extraction", st["extraction"], "hm³"],
        ["Annual extractable resource", st["resource"], "hm³"],
        ["Average stage of extraction", st["stage"], "%"],
        ["Category", st["category"], ""],
        ["Derived water level", st["water_level"]["value"], "m"],
    ]
    for i, row in enumerate(status_rows, 2):
        for c, v in enumerate(row, 1):
            ws.cell(row=i, column=c, value=v)
    for col, w in zip("ABC", (32, 18, 10)):
        ws.column_dimensions[col].width = w

    ws = sheet_with_header("Trend", ["Year", "Stage %", "Recharge (hm³)", "Extraction (hm³)"])
    for i, s in enumerate(report["trend"]["series"], 2):
        ws.cell(row=i, column=1, value=s["year"])
        ws.cell(row=i, column=2, value=s["stage"])
        ws.cell(row=i, column=3, value=s["recharge"])
        ws.cell(row=i, column=4, value=s["extraction"])
    for col, w in zip("ABCD", (10, 14, 18, 18)):
        ws.column_dimensions[col].width = w

    ws = sheet_with_header("Prediction", ["Year", "Stage %", "Lower", "Upper"])
    pr = report["prediction"]
    points = [{"year": p["year"], "value": p["value"], "lower": None, "upper": None} for p in pr["historical"] if p["year"] >= report["period"]["from"]] + list(pr["forecast"])
    for i, p in enumerate(points, 2):
        ws.cell(row=i, column=1, value=p["year"])
        ws.cell(row=i, column=2, value=round(p["value"], 2))
        ws.cell(row=i, column=3, value=round(p["lower"], 2) if p.get("lower") is not None else None)
        ws.cell(row=i, column=4, value=round(p["upper"], 2) if p.get("upper") is not None else None)
    meta_row = 2 + len(points) + 1
    for j, (k, v) in enumerate(
        [
            ("Model", pr.get("method_label")),
            ("Direction", pr["direction"]),
            ("R²", pr["r2"]),
            ("Projected change", pr["pct_change"]),
            ("Stage at " + str(pr["end_year"]), pr["end_value"]),
            ("Years to 100%", pr["years_to_threshold"]),
        ]
    ):
        ws.cell(row=meta_row + j, column=1, value=k).font = bold
        ws.cell(row=meta_row + j, column=2, value=v)
    for col, w in zip("ABCD", (12, 14, 14, 14)):
        ws.column_dimensions[col].width = w

    ws = sheet_with_header("Risk", ["Item", "Current", "Projected"])
    rs = report["risk"]
    for i, row in enumerate(
        [
            ["Category", rs["current_category"], rs["predicted_category"]],
            ["Risk level", rs["current"], rs["predicted"]],
        ],
        2,
    ):
        for c, v in enumerate(row, 1):
            ws.cell(row=i, column=c, value=v)
    ws.cell(row=5, column=1, value="Summary").font = bold
    ws.cell(row=5, column=2, value=rs["summary"]).alignment = wrap
    for col, w in zip("ABC", (18, 22, 22)):
        ws.column_dimensions[col].width = w

    ws = sheet_with_header("Recommendations", ["Recommendation"])
    for i, r in enumerate(report["recommendations"], 2):
        ws.cell(row=i, column=1, value=r).alignment = wrap
    ws.column_dimensions["A"].width = 80

    ws = sheet_with_header("Map Data", ["Name", "State", "District", "Stage %", "Category"])
    for i, f in enumerate(report["map"]["features"], 2):
        p = f.get("properties") or {}
        stage = p.get("stage_of_extraction") if p.get("stage_of_extraction") is not None else p.get("metric_value")
        ws.cell(row=i, column=1, value=p.get("name") or p.get("assessment_unit") or p.get("district") or "")
        ws.cell(row=i, column=2, value=p.get("state") or "")
        ws.cell(row=i, column=3, value=p.get("district") or "")
        ws.cell(row=i, column=4, value=round(stage, 2) if stage is not None else None)
        ws.cell(row=i, column=5, value=p.get("category") or "")
    for col, w in zip("ABCDE", (28, 18, 18, 12, 18)):
        ws.column_dimensions[col].width = w

    ws = sheet_with_header("Sources", ["Source"])
    for i, s in enumerate(report["sources"], 2):
        ws.cell(row=i, column=1, value=s).alignment = wrap
    ws.column_dimensions["A"].width = 100

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()