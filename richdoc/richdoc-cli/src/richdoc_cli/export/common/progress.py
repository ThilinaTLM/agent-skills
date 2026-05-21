"""Parse `<rd-progress value="…">` to a percentage + display string.

Mirrors the JS implementation in `richdoc.js` (`Ui` / `_rd-progress-value`)
so md / docx exports show the same number the browser does:

- ``"30%"``          → 30%      ``"30%"``
- ``"3/4"``          → 75%      ``"3 / 4"``
- ``"0.42"``         → 42%      ``"42%"``     (fraction in [0, 1])
- ``"80"``           → 80%      ``"80%"``     (already a percentage)
- ``"abc"``          → 0%       ``"abc"``     (fallback)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_RE_FRACTION = re.compile(r"^(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)$")
_RE_PERCENT = re.compile(r"^(-?\d+(?:\.\d+)?)\s*%$")


@dataclass(frozen=True)
class Progress:
    pct: float            # 0..100, clamped
    display: str          # what to render next to the bar


def parse_progress(raw: str | None) -> Progress:
    text = (raw or "").strip()
    if not text:
        return Progress(0.0, "0%")

    m = _RE_FRACTION.match(text)
    if m:
        num, denom = float(m.group(1)), float(m.group(2))
        if denom > 0:
            pct = max(0.0, min(100.0, num / denom * 100.0))
            # Render numerator/denominator with the cleanest form ("3/4"
            # not "3.0/4.0") — match the JS which echoes the parsed numbers.
            return Progress(pct, f"{_fmt(num)} / {_fmt(denom)}")

    m = _RE_PERCENT.match(text)
    if m:
        v = float(m.group(1))
        pct = max(0.0, min(100.0, v))
        return Progress(pct, f"{_fmt(v)}%")

    try:
        v = float(text)
    except ValueError:
        return Progress(0.0, text)

    if v > 1:
        pct = max(0.0, min(100.0, v))
    else:
        pct = max(0.0, min(1.0, v)) * 100.0
    return Progress(pct, f"{round(pct)}%")


def _fmt(n: float) -> str:
    """Render a number the way humans expect: drop a trailing `.0`."""
    if n == int(n):
        return str(int(n))
    return f"{n:g}"
