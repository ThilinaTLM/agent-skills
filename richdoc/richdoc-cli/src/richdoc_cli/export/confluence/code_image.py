"""Render a code block to a PNG.

Confluence's HTML importer strips `<pre>` / `<code>` block formatting on
upload — the visual rectangle, syntax colouring, and even indentation
collapse into plain prose. To preserve a real "this is code" affordance
we rasterise the block to a PNG and embed it via `<img>`.

The renderer is intentionally minimal: a header strip with title +
language tag, then one line per source line with Pygments token
colours mapped to RGB. It avoids fancy gutter chrome or window
decorations — readable, deterministic, low ceremony.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.token import Token
from pygments.util import ClassNotFound


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodeImageRequest:
    """One pending code block to rasterise."""

    text: str
    lang: str | None = None
    title: str | None = None
    line_numbers: bool = False


def render_code_image(
    text: str,
    *,
    lang: str | None = None,
    title: str | None = None,
    line_numbers: bool = False,
    style_name: str = "default",
    font_size: int = 16,
    max_width_px: int = 1600,
    scale: int = 2,
) -> bytes:
    """Rasterise `text` to a PNG. Returns the encoded bytes.

    Args:
        text: source as it should appear (already dedented).
        lang: pygments lexer name (``"python"``, ``"typescript"`` etc.).
            Unknown / empty → plain text rendering with no highlighting.
        title: optional header label (filename, caption).
        line_numbers: prefix every line with its 1-based index.
        style_name: pygments style ("default" / "monokai" / ...).
        font_size: nominal font size in points; multiplied by `scale`.
        max_width_px: soft cap on the body content width before scaling.
        scale: super-sampling factor (PNGs render at `scale`× the nominal
            size, so they look crisp when Confluence shrinks them to fit).
    """
    style = _safe_style(style_name)
    tokens = _tokenize(text, lang)
    font = _load_mono_font(font_size * scale)
    font_bold = _load_mono_font(font_size * scale, bold=True)

    # Editorial cream palette — matches the richdoc on-page aesthetic.
    bg = _hex("#FFFCF5")
    header_bg = _hex("#F4ECD8")
    header_fg = _hex("#3C2F1F")
    border = _hex("#E5D9B6")
    line_no_fg = _hex("#A89570")
    default_fg = _hex(style.style_for_token(Token.Text).get("color") or "222222")

    pad_x = 18 * scale
    pad_y = 14 * scale
    header_pad_y = 10 * scale
    line_gap = 4 * scale

    # Measure once to find the maximum line width and the per-line height.
    measure_img = Image.new("RGB", (1, 1))
    measurer = ImageDraw.Draw(measure_img)

    # Tokens grouped into one list-of-(text, style)-per-line.
    lines = _tokens_to_lines(tokens)
    if not lines:
        lines = [[("", Token.Text)]]

    n_lines = len(lines)
    gutter_w = 0
    if line_numbers:
        gutter_text = str(n_lines)
        gw = _text_width(measurer, gutter_text, font)
        gutter_w = gw + (12 * scale)

    line_h = _line_height(measurer, font) + line_gap

    # Max content width.
    content_w = 0
    for line in lines:
        w = 0
        for chunk_text, _ in line:
            w += _text_width(measurer, chunk_text, font)
        content_w = max(content_w, w)
    content_w = max(content_w, 200 * scale)
    content_w = min(content_w, max_width_px * scale)

    # Header sizing.
    header_text = _format_header(title, lang)
    has_header = bool(header_text)
    header_h = 0
    if has_header:
        header_h = _line_height(measurer, font_bold) + (header_pad_y * 2)

    total_w = pad_x * 2 + gutter_w + content_w
    total_h = header_h + (pad_y * 2) + (line_h * n_lines)

    img = Image.new("RGB", (total_w, total_h), bg)
    draw = ImageDraw.Draw(img)

    # Border + header strip.
    if has_header:
        draw.rectangle(
            [(0, 0), (total_w - 1, header_h - 1)], fill=header_bg
        )
        draw.line(
            [(0, header_h - 1), (total_w - 1, header_h - 1)],
            fill=border,
            width=max(1, scale // 2),
        )
        draw.text(
            (pad_x, header_pad_y),
            header_text,
            font=font_bold,
            fill=header_fg,
        )

    # Outer rounded-ish border (rectangle only — PIL has no native rounded
    # rect on every backend, and Confluence shrinks the image anyway).
    draw.rectangle(
        [(0, 0), (total_w - 1, total_h - 1)],
        outline=border,
        width=max(1, scale // 2),
    )

    # Body.
    body_y = header_h + pad_y
    for i, line in enumerate(lines):
        y = body_y + i * line_h
        x = pad_x
        if line_numbers:
            num = str(i + 1).rjust(len(str(n_lines)))
            draw.text((x, y), num, font=font, fill=line_no_fg)
            x += gutter_w
        for chunk_text, tok in line:
            color_hex = _color_for(style, tok)
            color = _hex(color_hex) if color_hex else default_fg
            draw.text((x, y), chunk_text, font=font, fill=color)
            x += _text_width(measurer, chunk_text, font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------


def _tokenize(text: str, lang: str | None) -> list[tuple[str, object]]:
    """Run Pygments lex if we have a lexer; otherwise return one big Text token."""
    if not text:
        return [("", Token.Text)]
    if lang:
        try:
            lexer = get_lexer_by_name(lang.strip().lower())
        except ClassNotFound:
            lexer = None
    else:
        lexer = None
    if lexer is None:
        return [(text, Token.Text)]
    # `lex` yields (Token, value) — keep the order.
    return [(value, tok) for tok, value in lex(text, lexer)]


def _tokens_to_lines(tokens: list[tuple[str, object]]) -> list[list[tuple[str, object]]]:
    """Split a flat token stream into a list of lines, preserving token style."""
    lines: list[list[tuple[str, object]]] = [[]]
    for text, tok in tokens:
        if not text:
            continue
        parts = text.split("\n")
        for idx, part in enumerate(parts):
            if part:
                lines[-1].append((_expand_tabs(part), tok))
            if idx != len(parts) - 1:
                lines.append([])
    # Drop a single trailing empty line (common when source ends with `\n`).
    if len(lines) > 1 and not lines[-1]:
        lines.pop()
    return lines


def _expand_tabs(s: str, tabsize: int = 4) -> str:
    return s.expandtabs(tabsize)


# ---------------------------------------------------------------------------
# Pygments style lookup
# ---------------------------------------------------------------------------


def _safe_style(name: str):
    try:
        return get_style_by_name(name)
    except ClassNotFound:
        return get_style_by_name("default")


def _color_for(style, tok) -> str | None:
    """Walk up the token hierarchy looking for a style with a colour."""
    cur = tok
    while cur is not None:
        spec = style.style_for_token(cur)
        if spec and spec.get("color"):
            return spec["color"]
        cur = cur.parent
    return None


# ---------------------------------------------------------------------------
# Font selection
# ---------------------------------------------------------------------------


_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "C:\\Windows\\Fonts\\consola.ttf",
    "C:\\Windows\\Fonts\\cour.ttf",
]

_FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf",
    "/Library/Fonts/Menlo Bold.ttf",
    "C:\\Windows\\Fonts\\consolab.ttf",
    "C:\\Windows\\Fonts\\courbd.ttf",
]


def _load_mono_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = _FONT_BOLD_CANDIDATES if bold else _FONT_CANDIDATES
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    # Last-resort fallback: PIL's bundled default (bitmap, no truetype).
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    if not text:
        return 0
    # Pillow 10+: textlength is the right call. Older fall-backs use textbbox.
    if hasattr(draw, "textlength"):
        return int(round(draw.textlength(text, font=font)))
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _line_height(draw: ImageDraw.ImageDraw, font) -> int:
    _, top, _, bottom = draw.textbbox((0, 0), "Ay", font=font)
    return bottom - top


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def _hex(text: str | None) -> tuple[int, int, int]:
    """Parse `#RRGGBB` / `RRGGBB` / `#RGB` into an RGB triple."""
    if not text:
        return (0x22, 0x22, 0x22)
    s = text.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return (0x22, 0x22, 0x22)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return (0x22, 0x22, 0x22)


def _format_header(title: str | None, lang: str | None) -> str:
    bits: list[str] = []
    if title:
        bits.append(title.strip())
    if lang:
        bits.append(lang.strip().upper())
    return "   ".join(bits)
