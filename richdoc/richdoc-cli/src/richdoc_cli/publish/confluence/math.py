"""Math → PNG via Kroki's TikZ endpoint.

Kroki's TikZ backend runs `pdflatex` against a full `standalone` LaTeX
document. A bare `\\begin{tikzpicture}…\\end{tikzpicture}` snippet is
rejected — we wrap the math source in a standalone TikZ math node so
display + inline expressions render uniformly.

Common Unicode glyphs (Σ, π, Δ, …) need a `\\DeclareUnicodeCharacter`
table because pdflatex defaults to OT1 input encoding. The table below
covers everything used by `examples/*.html`.

Returns None on any failure (network, server reject, non-PNG body).
"""

from __future__ import annotations

from urllib.error import URLError
from urllib.request import Request, urlopen


# Mapping of Unicode code points to LaTeX command, so pdflatex doesn't
# choke on UTF-8 math sources.
_UNICODE_DECLS: tuple[tuple[int, str], ...] = (
    (0x00B7, r"\cdot"),
    (0x00D7, r"\times"),
    (0x00F7, r"\div"),
    (0x2202, r"\partial"),
    (0x2208, r"\in"),
    (0x2209, r"\notin"),
    (0x2211, r"\sum"),
    (0x220F, r"\prod"),
    (0x221A, r"\sqrt{}"),
    (0x221E, r"\infty"),
    (0x2229, r"\cap"),
    (0x222A, r"\cup"),
    (0x2243, r"\simeq"),
    (0x2248, r"\approx"),
    (0x2260, r"\neq"),
    (0x2264, r"\leq"),
    (0x2265, r"\geq"),
    (0x2295, r"\oplus"),
    (0x2297, r"\otimes"),
    (0x2200, r"\forall"),
    (0x2203, r"\exists"),
    (0x2192, r"\rightarrow"),
    (0x2190, r"\leftarrow"),
    (0x21D2, r"\Rightarrow"),
    (0x21D4, r"\Leftrightarrow"),
    # Greek lowercase
    (0x03B1, r"\alpha"),
    (0x03B2, r"\beta"),
    (0x03B3, r"\gamma"),
    (0x03B4, r"\delta"),
    (0x03B5, r"\varepsilon"),
    (0x03B6, r"\zeta"),
    (0x03B7, r"\eta"),
    (0x03B8, r"\theta"),
    (0x03B9, r"\iota"),
    (0x03BA, r"\kappa"),
    (0x03BB, r"\lambda"),
    (0x03BC, r"\mu"),
    (0x03BD, r"\nu"),
    (0x03BE, r"\xi"),
    (0x03BF, "o"),
    (0x03C0, r"\pi"),
    (0x03C1, r"\rho"),
    (0x03C3, r"\sigma"),
    (0x03C4, r"\tau"),
    (0x03C5, r"\upsilon"),
    (0x03C6, r"\varphi"),
    (0x03C7, r"\chi"),
    (0x03C8, r"\psi"),
    (0x03C9, r"\omega"),
    # Greek uppercase
    (0x0393, r"\Gamma"),
    (0x0394, r"\Delta"),
    (0x0398, r"\Theta"),
    (0x039B, r"\Lambda"),
    (0x039E, r"\Xi"),
    (0x03A0, r"\Pi"),
    (0x03A3, r"\Sigma"),
    (0x03A6, r"\Phi"),
    (0x03A8, r"\Psi"),
    (0x03A9, r"\Omega"),
    # Misc
    (0x2026, r"\dots"),
    (0x00B1, r"\pm"),
    (0x00B0, r"^\circ"),
)


def render_math_png(
    source: str,
    *,
    endpoint: str = "https://kroki.io",
    timeout: float = 20.0,
) -> bytes | None:
    """Render LaTeX math `source` as a PNG using Kroki's TikZ backend."""
    text = (source or "").strip()
    if not text:
        return None
    doc = _build_tikz_document(text)
    url = f"{endpoint.rstrip('/')}/tikz/png"
    req = Request(
        url,
        data=doc.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Accept": "image/png",
            "User-Agent": "richdoc-publish/1.0",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — explicit user-supplied URL
            data = resp.read()
    except (URLError, TimeoutError, OSError, ValueError):
        return None
    if not data or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    return data


def _build_tikz_document(math_source: str) -> str:
    """Wrap a LaTeX math expression in a standalone TikZ document."""
    decls = "\n".join(
        rf"\DeclareUnicodeCharacter{{{cp:04X}}}{{{repl}}}"
        for cp, repl in _UNICODE_DECLS
    )
    return (
        r"\documentclass[border=2pt,12pt]{standalone}"
        "\n"
        r"\usepackage[utf8]{inputenc}"
        "\n"
        r"\usepackage{amsmath}"
        "\n"
        r"\usepackage{amssymb}"
        "\n"
        r"\usepackage{amsfonts}"
        "\n"
        r"\usepackage{tikz}"
        "\n"
        f"{decls}"
        "\n"
        r"\begin{document}"
        "\n"
        r"\begin{tikzpicture}"
        "\n"
        r"\node {$\displaystyle "
        f"{math_source}"
        r"$};"
        "\n"
        r"\end{tikzpicture}"
        "\n"
        r"\end{document}"
        "\n"
    )
