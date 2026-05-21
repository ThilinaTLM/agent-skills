# Changelog

## Unreleased

### Added

- **Prev/next chapter nav at the bottom of every book chapter** in
  `richdoc publish confluence`. Each chapter body now ends with a
  single-row `two_equal` layout-section: `← <prev>` + a yellow
  `PREVIOUS` Confluence Status lozenge in the left cell, and a green
  `NEXT` lozenge + `<next> →` in the right cell. Order follows the
  flattened `<rd-toc>` (depth-first, skipping group headers without an
  `href`). The first and last chapters get only the side they have a
  neighbour for; the empty side renders a placeholder so the layout
  stays two-column. Single-file mode emits no nav. The top of the page
  is unchanged — the existing rd-toc "Contents" block already gives
  readers a full chapter overview there.

### Changed

- **`richdoc publish confluence` is now configured exclusively via four
  environment variables**: `CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`,
  `CONFLUENCE_TOKEN`, and the new `CONFLUENCE_SPACE_KEY`. The CLI no
  longer accepts the `--site`, `--email`, `--token-stdin`, or
  `--space-key` flags, and no longer prompts on a TTY (no more
  `getpass`). When a required env var is missing, the CLI exits with
  the new `CONFIG_MISSING` error code and a structured `missing[]`
  field listing the unset vars so the calling agent can ask the user to
  export them. A present-but-malformed value still surfaces as
  `AUTH_ERROR`.

  `CONFLUENCE_SPACE_KEY` is required only by `pages` and `push`. The
  `spaces` and `page-by-id` subcommands need only the auth triple,
  preserving the discovery flow (running `spaces` to find a value for
  `CONFLUENCE_SPACE_KEY` would otherwise be paradoxical).

  Rationale: this CLI is driven by an agent, not a human at a TTY. A
  single env-var contract removes a category of "the agent passed the
  wrong flag" failures and makes credential setup a one-time user
  action.

  Migration:

  ```bash
  # before
  richdoc publish confluence push doc.html \
      --site https://acme.atlassian.net --email me@acme.com \
      --token-stdin --space-key DEV --parent-id 1234567

  # after
  export CONFLUENCE_SITE=https://acme.atlassian.net
  export CONFLUENCE_EMAIL=me@acme.com
  export CONFLUENCE_TOKEN=<token>
  export CONFLUENCE_SPACE_KEY=DEV
  richdoc publish confluence push doc.html --parent-id 1234567
  ```

  Internal API: `publish/confluence/auth.py` is gone. The replacement
  `publish/confluence/config.py` exposes `Config` / `ConfigError` /
  `resolve_config(required: tuple[str, ...])` and the constants
  `AUTH_VARS` / `PUBLISH_VARS`.

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

- **`richdoc export html`** (and its `export/html/` package). Richdoc
  files are already HTML — open the source `.html` directly in a
  browser. The bundler's one job was inlining relative assets into a
  self-contained `.bundle.html`, which conflated "export" with "asset
  packaging" and added a maintenance surface for a format the source
  already is. The remaining export targets are `md` and `docx`.
- **Dead `export/confluence/` package** (˜2.7k lines). The
  `html-confluence` CLI was removed earlier but the implementation
  files were left on disk. Nothing imported them; they referenced a
  CLI that no longer exists. Now actually gone.
- **Over-exported names in `publish/confluence/__init__.py`.** The
  package re-exported 19 symbols; the CLI only used 6. Trimmed
  `__all__` to the names `commands/publish.py` actually imports
  (`ConfluenceClient`, `ConfluenceError`, `CredentialError`, `Creds`,
  `PublishPlan`, `publish`, `resolve_creds`). Specific exception
  subclasses and storage-format helpers remain available from their
  defining modules.
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
