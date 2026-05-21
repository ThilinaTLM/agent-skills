"""Render LaTeX math to a PNG via Kroki's TikZ endpoint.

Confluence's HTML importer downgrades both block and inline equations to
plain text. To preserve them we rasterise LaTeX math to a PNG.

Kroki's ``tikz`` endpoint expects a full LaTeX document (it pipes the
source through pdflatex). We wrap the user's math in a single-line
``tikzpicture`` inside a ``standalone`` class that auto-sizes the PDF
crop to the rendered content.

Two practical caveats:

1. **Unicode in math.** pdflatex doesn't handle non-ASCII characters
   out of the box. We declare the handful that show up in real-world
   richdoc math (Σ, Δ, π, μ, …) via ``\\DeclareUnicodeCharacter`` so the
   common cases just work without escaping at authoring time.
2. **Fallback on failure.** ``render_to_png`` returns None when Kroki
   is unreachable, rate-limits us, or rejects the source. The caller
   (`handlers_rd._h_rd_math`) falls back to italic plain text.
"""

from __future__ import annotations

from ..common.diagrams import render_to_png


# Common unicode characters seen in richdoc math sources. Pdflatex maps
# them to the matching `\command` so non-ASCII source compiles without
# the author needing to think about LaTeX escapes.
_UNICODE_DECLARATIONS: dict[str, str] = {
    # Greek capitals
    "0391": "A",         "0392": "B",
    "0393": r"\ensuremath{\Gamma}",
    "0394": r"\ensuremath{\Delta}",
    "0395": "E",
    "0396": "Z",
    "0397": "H",
    "0398": r"\ensuremath{\Theta}",
    "0399": "I",
    "039A": "K",
    "039B": r"\ensuremath{\Lambda}",
    "039C": "M",
    "039D": "N",
    "039E": r"\ensuremath{\Xi}",
    "039F": "O",
    "03A0": r"\ensuremath{\Pi}",
    "03A1": "P",
    "03A3": r"\ensuremath{\Sigma}",
    "03A4": "T",
    "03A5": r"\ensuremath{\Upsilon}",
    "03A6": r"\ensuremath{\Phi}",
    "03A7": "X",
    "03A8": r"\ensuremath{\Psi}",
    "03A9": r"\ensuremath{\Omega}",
    # Greek lowercase
    "03B1": r"\ensuremath{\alpha}",
    "03B2": r"\ensuremath{\beta}",
    "03B3": r"\ensuremath{\gamma}",
    "03B4": r"\ensuremath{\delta}",
    "03B5": r"\ensuremath{\varepsilon}",
    "03B6": r"\ensuremath{\zeta}",
    "03B7": r"\ensuremath{\eta}",
    "03B8": r"\ensuremath{\theta}",
    "03B9": r"\ensuremath{\iota}",
    "03BA": r"\ensuremath{\kappa}",
    "03BB": r"\ensuremath{\lambda}",
    "03BC": r"\ensuremath{\mu}",
    "03BD": r"\ensuremath{\nu}",
    "03BE": r"\ensuremath{\xi}",
    "03BF": "o",
    "03C0": r"\ensuremath{\pi}",
    "03C1": r"\ensuremath{\rho}",
    "03C3": r"\ensuremath{\sigma}",
    "03C4": r"\ensuremath{\tau}",
    "03C5": r"\ensuremath{\upsilon}",
    "03C6": r"\ensuremath{\varphi}",
    "03C7": r"\ensuremath{\chi}",
    "03C8": r"\ensuremath{\psi}",
    "03C9": r"\ensuremath{\omega}",
    # Math operators / common glyphs
    "2200": r"\ensuremath{\forall}",
    "2203": r"\ensuremath{\exists}",
    "2205": r"\ensuremath{\emptyset}",
    "2208": r"\ensuremath{\in}",
    "2209": r"\ensuremath{\notin}",
    "220B": r"\ensuremath{\ni}",
    "2212": "-",
    "2218": r"\ensuremath{\circ}",
    "221A": r"\ensuremath{\sqrt{}}",
    "221E": r"\ensuremath{\infty}",
    "2227": r"\ensuremath{\wedge}",
    "2228": r"\ensuremath{\vee}",
    "2229": r"\ensuremath{\cap}",
    "222A": r"\ensuremath{\cup}",
    "2248": r"\ensuremath{\approx}",
    "2260": r"\ensuremath{\neq}",
    "2264": r"\ensuremath{\leq}",
    "2265": r"\ensuremath{\geq}",
    "2282": r"\ensuremath{\subset}",
    "2286": r"\ensuremath{\subseteq}",
    "2192": r"\ensuremath{\to}",
    "21D2": r"\ensuremath{\Rightarrow}",
    "21D4": r"\ensuremath{\Leftrightarrow}",
    "00B1": r"\ensuremath{\pm}",
    "00D7": r"\ensuremath{\times}",
    "00F7": r"\ensuremath{\div}",
    "00B0": r"\ensuremath{^\circ}",
    "2022": r"\ensuremath{\bullet}",
    "00B7": r"\ensuremath{\cdot}",
    "2026": r"\ensuremath{\dots}",
}


def _build_unicode_preamble() -> str:
    return "\n".join(
        f"\\DeclareUnicodeCharacter{{{code}}}{{{repl}}}"
        for code, repl in _UNICODE_DECLARATIONS.items()
    )


_UNICODE_PREAMBLE = _build_unicode_preamble()


def render_math_image(
    latex: str,
    *,
    display: str = "block",
    endpoint: str = "https://kroki.io",
    timeout: float = 20.0,
) -> bytes | None:
    """Render `latex` to PNG. Returns the PNG bytes or None on failure.

    Args:
        latex: math source as the user wrote it inside `<rd-math>`.
            Display-mode wrapping (`$$`, `\\[`) is added here — the
            user's source is the bare math body.
        display: ``"block"`` for centred display math, ``"inline"`` for
            text-flow math. Affects only the rendering scale, not the
            output dimensions (the caller positions the resulting img).
        endpoint: Kroki base URL.
        timeout: HTTP timeout in seconds.
    """
    src = (latex or "").strip()
    if not src:
        return None
    body = src.replace("\r\n", "\n").strip()
    if display == "inline":
        scale = 1.6
        math = f"${body}$"
    else:
        scale = 2.2
        math = f"$\\displaystyle {body}$"
    tex = (
        "\\documentclass[border=2pt]{standalone}\n"
        "\\usepackage{tikz}\n"
        "\\usepackage{amsmath,amssymb,amsfonts}\n"
        f"{_UNICODE_PREAMBLE}\n"
        "\\begin{document}\n"
        "\\begin{tikzpicture}\n"
        f"  \\node[inner sep=2pt,text=black,scale={scale}] {{{math}}};\n"
        "\\end{tikzpicture}\n"
        "\\end{document}\n"
    )
    return render_to_png(tex, kind="tikz", endpoint=endpoint, timeout=timeout)
