"""Parse the `data` attribute / text content of an `<rd-chart>`.

The browser-side renderer uses Observable Plot to draw an actual chart.
The export pipelines (markdown, docx) downgrade to a tabular fallback
since neither format has a native plot primitive that survives an LLM
context window or a Word import.

This module is the shared parser. It recognises three shapes:

- JSON list of dicts:     `[{"x": 1, "y": 2}, …]`           → keys = first row
- JSON list of scalars:   `[1, 2, 3]`                       → keys = ["value"]
- CSV (line-separated):   `"x,y\\n1,2\\n3,4"`               → first line = header
- Numeric comma list:     `"1, 2, 3"`                       → keys = ["#", "value"]

Returns `None` when the input doesn't fit any known shape — the caller
falls back to dumping the raw text as a code block.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChartTable:
    """A 2-d table extracted from an rd-chart `data` attribute / body."""

    headers: list[str]
    rows: list[list[str]]


def parse_chart(raw: str) -> ChartTable | None:
    raw = (raw or "").strip()
    if not raw:
        return None

    # JSON shape
    if raw.startswith("[") or raw.startswith("{"):
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                if not all(isinstance(row, dict) for row in data):
                    return None
                keys = list(data[0].keys())
                headers: list[str] = [str(k) for k in keys]
                rows: list[list[str]] = [
                    [str(row.get(k, "")) for k in keys] for row in data
                ]
            else:
                headers = ["value"]
                rows = [[str(v)] for v in data]
            return ChartTable(headers=headers, rows=rows)

    # CSV shape (line-separated, with commas on the first line). Rows are
    # returned at their natural width — callers pad to header width with
    # whatever filler suits their renderer.
    if "\n" in raw and "," in raw:
        line_rows = [r.split(",") for r in raw.splitlines() if r.strip()]
        if line_rows:
            headers: list[str] = [str(c.strip()) for c in line_rows[0]]
            rows: list[list[str]] = [[str(c.strip()) for c in r] for r in line_rows[1:]]
            return ChartTable(headers=headers, rows=rows)

    # Plain numeric comma list
    if re.fullmatch(r"[\d\s,.\-eE]+", raw):
        values = [v.strip() for v in raw.split(",") if v.strip()]
        return ChartTable(
            headers=["#", "value"],
            rows=[[str(i), v] for i, v in enumerate(values, start=1)],
        )

    return None
