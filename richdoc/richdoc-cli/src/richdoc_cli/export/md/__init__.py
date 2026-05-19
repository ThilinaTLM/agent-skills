"""Markdown export package.

Public entry point: `html_to_markdown(source, ...) -> (markdown, dropped)`.
Importing this package triggers handler registration as a side-effect.
"""

from . import handler_table  # noqa: F401 — side-effect: populate HANDLERS
from .converter import html_to_markdown

__all__ = ["html_to_markdown"]
