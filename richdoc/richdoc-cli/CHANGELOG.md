# Changelog

## Unreleased

### Added

- **`richdoc publish confluence` — push richdoc HTML into an existing
  Confluence Cloud space via the REST API.** Replaces the abandoned
  `html-confluence` zip exporter (the import path could only create new
  spaces, never update existing pages). Four subcommands:

  - `richdoc publish confluence spaces [-q TEXT]` — list spaces the
    token can see.
  - `richdoc publish confluence pages --space-key KEY [-q TEXT] [--parent-id ID]`
    — list pages in a space.
  - `richdoc publish confluence page-by-id PAGE_ID` — resolve a page id.
  - `richdoc publish confluence push INPUT --space-key KEY […]` —
    publish a single-file doc or whole book to that space; create or
    update by `(space, parent, title)`. Use `--page-id ID` to force a
    specific page, `--parent-id ID` / `--parent-title TEXT` to pick the
    parent, `--title-prefix TEXT` to namespace pages, `--dry-run` to
    inspect the storage XML + attachment plan without calling write
    endpoints.

  **Native Confluence rendering** — no more PNG-soup. Each component
  maps to the storage-format primitive Confluence's editor uses:

  - `rd-code` / `rd-diff` / `rd-shell` → `code` macro (real syntax
    highlighting, copy button, language pill).
  - `rd-callout` / `rd-banner` → native `info` / `note` / `warning` /
    `tip` macros with the appropriate side bar.
  - `rd-detail` → native `expand` macro (collapsibility preserved!).
  - `rd-checklist` → native `<ac:task-list>` (interactive checkboxes
    that sync state in Confluence).
  - `rd-math` / `rd-diagram` → Kroki PNG → page attachment →
    `<ac:image><ri:attachment/>` reference. Attachments use stable
    `math-<sha1>.png` / `diag-<sha1>.png` filenames so re-publishing
    versions them in place.
  - Tables, lists, headings, blockquotes, `<code>`, `<img>` → native
    XHTML. Images upload via the v1 `PUT /child/attachment` endpoint
    (idempotent by filename).
  - `rd-toc` is dropped — Confluence's native sidebar already shows
    the page tree.

  **Book mode** preserves the chapter tree natively: the entry chapter
  lives under the user-supplied `--parent-id`; every other chapter
  nests under either its TOC-resolved parent or the entry chapter as a
  fallback. Confluence's sidebar shows the full hierarchy.

  **Auth model** — nothing persisted to disk. Resolution order for
  each credential: explicit flag (`--site`, `--email`, `--token-stdin`)
  → env var (`CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`, `CONFLUENCE_TOKEN`)
  → interactive prompt (`getpass` for the token). Non-TTY runs error
  out rather than block on a prompt.

  **Re-runs are idempotent.** Pages match by `(space, parent, title)`
  triple; attachments match by filename; PNGs derive their filename
  from a content hash so identical re-renders skip uploads.

  No new runtime dependencies — the REST client is stdlib `urllib` +
  `email.mime`. The Pillow + Pygments deps the old `html-confluence`
  needed are gone.

### Removed

- **`richdoc export html-confluence`** (and its `export/confluence/`
  package). The Confluence HTML-import path always creates a *new*
  space, never lets you update an existing one — dead-end for any
  ongoing workflow. The `richdoc publish confluence` command above is
  the replacement.
- Runtime dependencies `pillow` and `pygments` are gone with it; the
  native code/callout/expand macros in `publish confluence` render
  better in Confluence than rasterised PNGs ever could.
- New error codes in the JSON envelope: `AUTH_ERROR`,
  `PERMISSION_DENIED`, `NOT_FOUND`, `VERSION_CONFLICT`,
  `ATTACHMENT_TOO_LARGE`, `UPSTREAM_ERROR`, `AMBIGUOUS_MATCH`.

### Fixed

- **`rd-code` / `rd-diff` / `rd-shell` were heavily over-indented in
  DOCX.** The `_dedent` helper only stripped common *space* prefixes, so
  source HTML that nested `<rd-code>` inside `<rd-section>` (the common
  case) left every code line prefixed with the surrounding tabs —
  python-docx then emitted them as stacked `<w:tab/>` runs, shifting
  each line 3+ tab-stops to the right. `_dedent` now strips both spaces
  and tabs, matching the md exporter and the runtime KaTeX/k() helper.

- **`rd-math` rendered as raw LaTeX source in monospace.** The handler
  dumped `\frac{...}` literally into a `RichdocCode`-styled paragraph,
  which made block math unreadable and broke the Confluence import
  workflow (no editable equation). LaTeX is now converted via
  `latex2mathml` and Microsoft's MML2OMML XSLT into Word's native OMML
  format, so block and inline `<rd-math>` land as real Word equations
  that Confluence preserves on import. Unsupported LaTeX falls back to
  italic Cambria Math source.

### Internal

- New `export/docx/math.py` owns the LaTeX→OMML pipeline; the
  Microsoft-shipped `mml2omml.xsl` (TEI BSD-2-Clause) is bundled
  alongside it. `_Run` gained an optional `omath` field so inline math
  can splice an `<m:oMath>` directly into the paragraph XML.

- New runtime dependency: `latex2mathml>=3.77` (MIT, pure Python).

## 0.5.1

### Fixed

- **`rd-progress` rendered as `8000%` in markdown.** Bare numeric values
  (`<rd-progress value="80">`) were unconditionally multiplied by 100.
  Parser now matches the JS behavior: values > 1 are treated as already
  being percentages, values ≤ 1 as fractions. Shared helper at
  `export/common/progress.py` keeps md and docx in sync.

- **`rd-progress` showed a bare numeric value in DOCX** (`Coverage: 80`).
  Now renders as `Coverage: 80%` using the same shared parser.

- **`rd-steps` body text was dropped in DOCX.** The previous walker only
  visited element children, so text nodes around inline tags (e.g. the
  `"Run "` and `"."` around `<code>richdoc new</code>`) disappeared and
  steps with no inline elements rendered with empty bodies. Step bodies
  now split into inline runs (joined to the list-item paragraph with an
  em-dash separator) and block children (rendered as follow-on
  paragraphs).

- **`rd-callout` body paragraphs were duplicated in DOCX.** The handler
  emitted `_inline_runs` of the entire element *and* re-emitted each
  block child. Callouts with block children now skip the inline pass;
  inline-only callouts still get a single combined run.

- **`rd-pros-cons` produced an awkward zipped table in DOCX** where
  unrelated pros and cons shared rows and asymmetric lists left empty
  cells. Pros and cons now render as two stacked sections (heading +
  bulleted list each), matching the `rd-cols` linearisation convention.

- **`richdoc export md -o -` created a literal file named `-`** instead
  of writing to stdout. The `cmd_md` Click handler now mirrors `cmd_html`
  / `cmd_docx`: `-o -` writes the markdown to stdout in single mode,
  errors out in multi mode, and skips asset materialisation. New
  `export.md.pipeline.render_to_string` helper backs the stdout path.

### Internal

- New `export/common/progress.py` shared between md and docx exporters.
- New `export/md/pipeline.render_to_string()` for filesystem-free
  markdown generation.

## 0.5.0

Initial tagged release covered by this changelog.
