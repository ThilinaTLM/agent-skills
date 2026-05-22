"""`richdoc lint` package.

Public surface:

- ``lint_path(path, *, fix)`` \u2014 the programmatic entry point used by
  the click command and by ``publish confluence push`` for its
  pre-publish lint pass.
- ``cmd`` \u2014 the click command itself (``richdoc lint``).

Everything else lives behind underscored module-internal helpers:

- ``runner``    \u2014 file walker, ``_lint_file``, the per-file envelope.
- ``issues``    \u2014 issue-building helpers + project-wide constants
                  (``REMOVED_TAGS``, attribute allow-lists, regexes).
- ``rules.document``    \u2014 doc-level checks (missing CSS / JS / rd-page).
- ``rules.attributes``  \u2014 per-element schema checks.
- ``rules.hero_nav``    \u2014 book-mode ``hero-nav-redundant`` rule + fix data.
- ``rules.book``        \u2014 book-mode ``book-toc-drift`` detection.
- ``autofix``           \u2014 source rewriter used by ``--fix``.
"""

from .cli import cmd
from .runner import lint_path

__all__ = ["cmd", "lint_path"]
