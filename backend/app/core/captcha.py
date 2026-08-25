"""Self-hosted CAPTCHA for public signup — no external service, no API key.

A signed arithmetic question rendered as a noisy SVG. The captcha id is
HMAC-signed with JWT_SECRET and carries its own expiry, so verification is
stateless (works across workers/containers) and tamper-proof:

    id = base64url({a, op, b, exp}) + "." + HMAC(body)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import secrets
import time

from app.config import get_settings

_TTL_SECONDS = 600


def _secret() -> bytes:
    return get_settings().JWT_SECRET.encode()


def _sign(body: str) -> str:
    return hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()


def _constant_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def generate() -> tuple[str, str, int]:
    """Return ``(captcha_id, question_text, answer)``."""
    rng = random.SystemRandom()
    a = rng.randint(2, 9)
    b = rng.randint(2, 9)
    if rng.random() < 0.5 or a < b:
        op = "+"
        answer = a + b
        if a < b:
            a, b = b, a
            answer = a + b
    else:
        op = "-"
        answer = a - b
    exp = int(time.time()) + _TTL_SECONDS
    nonce = secrets.token_hex(8)
    body = json.dumps(
        {"a": a, "op": op, "b": b, "exp": exp, "n": nonce}, separators=(",", ":")
    )
    cid = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=") + "." + _sign(body)
    question = f"{a} {op} {b}"
    return cid, question, answer


def verify(captcha_id: str | None, answer: str | int | None) -> bool:
    """Constant-time, single-field validation of a captcha response."""
    if not captcha_id or answer is None:
        return False
    try:
        raw_b64, sig = captcha_id.rsplit(".", 1)
        padded = raw_b64 + "=" * (-len(raw_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        body = json.dumps(
            {
                "a": payload["a"],
                "op": payload["op"],
                "b": payload["b"],
                "exp": payload["exp"],
                "n": payload.get("n", ""),
            },
            separators=(",", ":"),
        )
    except Exception:  # noqa: BLE001 - malformed ids simply fail
        return False
    if not _constant_eq(_sign(body), sig):
        return False
    if int(payload.get("exp", 0)) < int(time.time()):
        return False
    try:
        given = int(str(answer).strip())
    except ValueError:
        return False
    expected = (
        payload["a"] + payload["b"]
        if payload["op"] == "+"
        else payload["a"] - payload["b"]
    )
    return given == expected


def render_svg(question: str) -> str:
    """Noisy SVG of the arithmetic question — hard to scrape, cheap to render."""
    rng = random.Random(question)  # deterministic per question
    chars = []
    x = 14
    for ch in question.replace(" ", ""):
        y = 30 + rng.randint(-6, 6)
        rot = rng.randint(-22, 22)
        colour = rng.choice(["#0e7490", "#155e75", "#1d4ed8", "#334155"])
        chars.append(
            f'<text x="{x}" y="{y}" fill="{colour}" font-size="26" '
            f'font-family="monospace" font-weight="bold" '
            f'transform="rotate({rot} {x} {y})">{ch}</text>'
        )
        x += 24 if ch.isdigit() else 26
    lines = []
    for _ in range(4):
        x1, y1, x2, y2 = rng.randint(0, 130), rng.randint(0, 44), rng.randint(0, 130), rng.randint(0, 44)
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#94a3b8" stroke-width="1" opacity="0.55"/>'
        )
    dots = []
    for _ in range(26):
        dots.append(
            f'<circle cx="{rng.randint(0, 132)}" cy="{rng.randint(0, 46)}" '
            f'r="{rng.uniform(0.7, 1.6):.1f}" fill="#64748b" opacity="0.5"/>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="140" height="48" '
        'role="img" aria-label="captcha">'
        '<rect width="100%" height="100%" fill="#f1f5f9"/>'
        + "".join(lines)
        + "".join(dots)
        + "".join(chars)
        + "</svg>"
    )
