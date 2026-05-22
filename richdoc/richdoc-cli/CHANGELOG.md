# Changelog

## Unreleased

### Breaking changes

- **Confluence commands moved to `richdoc confluence ...`.** The old
  `richdoc publish confluence ...` group was removed. Use
  `richdoc confluence spaces`, `richdoc confluence pages`,
  `richdoc confluence page-by-id`, and
  `richdoc confluence publish INPUT`. The former `push` subcommand is
  now `publish`.

### Developer experience

- **Test + lint baseline.** Adds a `[project.optional-dependencies]
dev` group (pytest, syrupy, ruff, mypy, lxml-stubs) plus ruff, mypy,
and pytest config in `pyproject.toml`. Run the gates with
`uv run ruff check src tests`, `uv run mypy src`, and
`uv run pytest`. See `tests/README.md` for the snapshot conventions.
- **Snapshot test suite (91 tests / 49 snapshots).** Locks every
  command's JSON envelope against the reference fixtures in
  `richdoc/examples/`, plus broken / drift / autofix fixtures in
  `richdoc-cli/tests/fixtures/`. DOCX output is captured as a
  semantic summary; Confluence storage XML is pretty-printed and
  local-ids stabilised before comparison. Dry-run publish tests
  patch the client to keep CI offline.
- **Pre-commit hooks** (`.pre-commit-config.yaml`) replace CI as the
  enforcement point for the gates. Local `pre-commit install` wires
  ruff + mypy + pytest (CLI) and biome + tsc + vitest (lib) into
  `git commit`, plus a small set of hygiene hooks (trailing
  whitespace, EOF newlines, YAML / TOML well-formedness,
  merge-conflict markers, large-file guard). Every hook is scoped
  to `^richdoc/` so the other skill subtrees in this repo are
  untouched.
- **Lib-side tooling parity.** `richdoc-lib/package.json` gains a
  `typecheck` script and vitest as a dev dep, plus a smoke test
  for the schema registry. `pnpm test`, `pnpm typecheck`, and
  `pnpm lint` are all run in CI alongside `pnpm build`.

### Changed

- **`<rd-prefs>` schema.** `customChildren` was set to the literal
  string `"none"`, which fell outside the documented TagSpec union
  and was silently ignored by the linter. It's now an empty array
  `[]`, which makes the linter enforce "no rd-* children allowed"
  on `<rd-prefs>`. The element is JS-injected and has no children
  in any known document, so this is a no-op for existing usage.
- **Lib registry consolidation.** `schema-registry.ts` no longer
  hand-lists every child tag (`kv.rowSpec`, `compare.cellSpec`, …).
  Each component's `.schema.ts` now exports a `bundle: SchemaBundle`
  that carries the parent tag plus a declarative `childTags` array;
  `schema-registry.ts` flat-maps the bundles in canonical vocabulary
  order. Adding or renaming a child tag touches exactly one file.
  The emitted `assets/schema.json` is byte-identical to the previous
  build.
- **`commands/lint.py` split into `lint/` package** (949 → 10 focused
  files). `commands/lint.py` is now a 3-line shim re-exporting
  `lint_path` / `cmd`. The real implementation lives behind:
  - `lint/cli.py` (click wiring),
  - `lint/runner.py` (file walker + per-file envelope),
  - `lint/issues.py` (`add_issue` helper + project-wide constants),
  - `lint/rules/{document,attributes,book,hero_nav}.py` (per-rule
    modules; each rule appends to a shared ``issues`` list),
  - `lint/autofix.py` (the source rewriter used by `--fix`).
  No file in the new package exceeds 320 lines; rule additions touch
  exactly one file.
- **`publish/confluence/converter.py` split** (725 → 214 + 6 focused
  sidecars). The converter state machine is now in `state.py`; XML
  escape helpers in `xml.py`; layout post-processing in `layout.py`;
  the book-mode prev/next nav in `nav.py`; bibliography rendering in
  `refs.py`; title resolution in `titles.py`. `converter.py` keeps
  the public `html_to_storage` entry, the `StorageResult` /
  `PendingAttachment` / `TocEntry` dataclasses, and `dedent`, and
  re-exports the most-used names so handler files keep their
  existing imports.
- **Confluence subcommands moved to `publish/confluence/cli.py`**
  (442 → 23 + 440). `commands/publish.py` is now just the top-level
  click group; the four Confluence subcommands (`spaces`, `pages`,
  `page-by-id`, `push`) live next to the rest of the Confluence
  integration so changes to the publisher don't have to round-trip
  through `commands/`. New publish targets follow the same pattern
  (create `publish/<target>/cli.py` and attach the group).

- **Shared exporter utilities** (`export.common`). The three exporter
  pipelines (md / docx / publish-confluence) had accumulated
  near-duplicate copies of foundational helpers; consolidating them
  removes ~150 lines of drift-prone code:
  - `export/common/href.py` — single `is_external_href` implementation
    (replaces the duplicate `_is_external` in
    `publish/confluence/pipeline.py`).
  - `export/common/text.py` — single `dedent` (replaces three
    near-identical local copies in md / docx / confluence).
  - `export/common/titles.py` — single `resolve_doc_title` +
    `chapter_label` (replaces four near-identical copies). The
    Confluence publisher passes
    `normalize_whitespace_in_hero=True` because page titles must be
    single-line; everyone else gets the raw author-typed value.
  - `export/common/references.py` — single `format_ref` with a
    pluggable `RefRenderer` (replaces the md and Confluence copies).
    The docx exporter still builds runs directly and is not consumed.
- **`commands/_safe.py` decorator** (`safe_command` + `write_or_error`).
  Every click command now ends in a single ``@safe_command`` decorator
  that catches ``FileExistsError`` (→ ``FILE_EXISTS``),
  ``SchemaLoadError`` (→ ``INPUT_ERROR``),
  ``ConfluenceError`` (→ its own ``code``), and bare ``OSError``
  (→ ``INPUT_ERROR``). Write-step ``OSError``s that need ``OUTPUT_ERROR``
  route through ``write_or_error(action)``. Removed roughly 80 lines
  of repeated ``try`` / ``except`` boilerplate across
  ``new`` / ``init`` / ``components`` / ``update`` / ``lint`` /
  ``export md`` / ``export docx`` and all four ``publish confluence``
  subcommands.

### Deferred follow-ups

Family-by-family splits of `publish/confluence/handlers_rd.py`
(1346 L), `export/docx/handlers_rd.py` (748 L), and
`export/md/handlers_rd.py` (648 L) were considered but skipped:
each file is already grouped by explicit section markers and the
handlers are self-contained per-section. The remaining LOC count
is defensible reading material, not coupled complexity. Revisit
after Phase 7's converter consolidation.
- **Schema-cache helper.** `richdoc_cli.schema.load_schema` is now
  `@functools.cache`-d; tests that need a fresh read call
  `load_schema.cache_clear()`.
- **`text_of`, `iter_text`, `sourceline_of` helpers** in
  `export.common.walker` replace ad-hoc `"".join(el.itertext())` /
  `el.sourceline` reads. The new helpers narrow lxml's
  `Iterator[str | bytes]` and `EllipsisType` types so call sites stay
  type-clean.

### Added

- **`book-toc-drift` lint rule.** When a file's `<rd-toc>` lists other
  chapters on disk, each linked file must carry a matching `<rd-toc>`
  block. Mismatched, missing, added, or reordered chapters surface as
  an error with a structured per-entry `diff[]` (each item gives an
  index path through the chapter tree plus a short detail). Hrefs are
  compared by resolved filesystem target, so `./other.html` from the
  book root and `../other.html` from a subdirectory are equivalent.
  Drift is **not autofixed** — the agent reconciles the canonical
  block manually.

- **`hero-nav-redundant` lint rule + `--fix` autofix.** When book mode
  is active and `<rd-hero>` contains hand-written prev/next links, the
  rule fires once per offending element. The detection is:

  - Any `<a>` child whose `href` resolves to another book chapter, or
    whose text matches `prev|previous|next|up|home|index|←|↑|→|↓`.
  - Any `Prev:/Previous:/Next:/Up:` segment in the hero's `meta`
    attribute.

  `richdoc lint --fix` strips the matched children and segments in
  place, recording each fix in the envelope's `fixed[]` array. The
  Digital Pod feedback case (11 chapters, 38 redundant nav items)
  fixes in one command.

- **`richdoc lint <dir>`.** The `lint` command now accepts a directory;
  every `*.html` file inside is linted and the results aggregated into
  a `files[]` array with the same per-file shape as the single-file
  envelope. Per-file `errors[]` / `warnings[]` are summed at the top
  level. Used by the publisher's pre-publish lint and by
  `richdoc lint --fix <dir>` for batch cleanup.

- **Pre-publish lint in `richdoc publish confluence push`.** `push`
  now runs `richdoc lint` against the input (file or directory) before
  any create / update / upload call. Errors block with the new
  `LINT_ERRORS` envelope code; warnings do not. Pass `--no-lint` to
  bypass when intentionally debugging a publish.

- **`richdoc publish confluence push` accepts a directory.** Resolves
  the entry chapter as `<dir>/index.html`. Missing `index.html` fails
  fast with `INVALID_PARAMS` — book mode has no syntactic difference
  between an entry chapter and any other chapter, so the CLI refuses
  to guess. The complete migration of a flat doc set to a published
  book is now:

  ```bash
  richdoc lint docs/ --fix              # strip legacy hero nav
  richdoc publish confluence push docs/ # auto-lint, then publish
  ```

- **`references/migrating-to-book-mode.md`.** Five-step walkthrough
  for converting an existing flat HTML doc set into a richdoc book.

### Changed

- **Confluence converter: content tables get content-derived column widths.**
  `<table>`, `<rd-compare>`, `<rd-rubric>`, and non-sparkline
  `<rd-chart>` now emit `<table data-layout="default">` plus a generated
  `<colgroup>` whose widths follow visible text length. That gives short
  label columns less space and prose columns more space, matching the
  auto-fit feel of the existing `<rd-kv>` tables. The previous bare
  `<table>` form forced equal-width columns regardless of cell size.
  `<rd-kv>` and `<rd-api>` keep their explicit 200px / 760px colgroup —
  that's still the right shape for spec blocks where the key column
  should be narrow.

- **`_h_rd_hero` (Confluence converter) splits eyebrow/lede/meta into
  separate paragraphs.** The previous renderer joined all three into
  a single `<p><em>eyebrow · lede · meta</em></p>` blob, which made
  long lede + meta combinations unreadable. The new output is four
  blocks: `<p><strong>eyebrow</strong></p>` + `<h1>title</h1>` +
  `<p><em>lede</em></p>` + `<p><em>meta</em></p>`, mirroring the
  HTML view's hero structure.

- **Renderer guards drop legacy `<rd-hero>` nav in book mode.** Both
  `hero.ts` (HTML view) and the Confluence converter silently filter
  `<a>` children whose href resolves to a book chapter, or whose text
  matches the legacy nav pattern. The Confluence converter also
  scrubs `Prev:/Next:/Up:` segments out of the hero's `meta` attribute
  and records dropped children as `rd-hero/a` entries in the publish
  envelope's `dropped[]`. The lint rule `hero-nav-redundant` catches
  the same patterns at authoring time; the renderer guards exist so
  pre-existing docs render cleanly without re-authoring.

- **`export/book.py` exports book-mode helpers.** `find_book_toc`,
  `chapter_title`, `toc_signature`, `linked_chapter_paths`, and
  `is_external_href` were promoted from private to public so lint and
  any future tooling share one definition of "a book." `TocSignature`
  / `TocSignatureEntry` dataclasses are new — immutable, equality-
  comparable normalisations of an `<rd-toc>` tree.

### Documentation

- **`SKILL.md`** — updated the `lint` and `publish confluence` rows in
  the CLI table; expanded the Books section to mention the new lint
  rules and the auto-lint preflight on push.
- **`references/multi-file-books.md`** — new "How book discovery
  works" section walks through the runtime + lint + publish contract.
  Authoring rules updated for the two new lint rules. Cross-link to
  the migration guide.
- **`references/publish.md`** — documents the directory form of
  `push`, the pre-publish lint pass, the new `--no-lint` flag, the
  `LINT_ERRORS` error code, the new hero rendering, and the book-mode
  hero-nav drop behaviour (visible as `rd-hero/a` in `dropped[]`).

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
