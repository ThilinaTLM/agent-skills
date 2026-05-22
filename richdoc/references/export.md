# richdoc — export reference

The richdoc CLI ships three export targets:

- **`md`** — GitHub-flavoured Markdown.
- **`docx`** — Word document for editing in Word / LibreOffice.
- **`confluence`** — offline storage bundle (`richdoc.confluence.bundle.v1`)
  consumed by the separate `confluence` skill. See the Confluence
  section below.

There is no `html` export target: richdoc files are already HTML. Open
the source `.html` directly in a browser. Anything else (PDF, EPUB,
etc.) is out of scope — generate from one of these.

The `md` / `docx` subcommands share a `--single` / `--multi` flag pair so the output shape is explicit:

- `--single` — one output file containing the whole book.
- `--multi`  — one output file per chapter, mirroring the source tree under a folder.

Defaults match the format: `md` defaults to `--multi`, `docx` defaults to `--single`. For a non-book input both modes still work (multi produces a folder with one file). The two flags are mutually exclusive. The JSON envelope reports the resolved `mode`.

`--no-book` overrides auto-detection and renders only the entry file, regardless of the mode flag.

## `richdoc export md <file> [-o <path>] [--single|--multi]`

**Default (`--multi`)** writes a folder. Default location: `<input-stem>-md/`. Layout:

```
<out>/
  <stem>.md             # single-file input
  01-chapter.md         # one .md per chapter for a book
  ops/runbook.md        # subdirectories preserved
  assets/
    <hash>.png
    …
```

**`--single`** writes one combined `.md`. Default location: `<input-stem>.md`. The combined file has a single `# Book title` H1, a `## Contents` block linking each chapter, then every chapter's body with all headings demoted by one level (so each chapter sits at `##`). The shared `<rd-toc>` in each chapter is stripped (the `## Contents` block already covers it). Page-rule `---` separators between chapters. Assets land in a single `assets/` directory next to the output `.md`.

`-o -` writes the markdown to stdout (single mode only).

Every `rd-*` component maps to the closest markdown idiom: callouts to GFM admonitions (`> [!NOTE]`), `rd-compare` / `rd-rubric` / `rd-api` to tables, `rd-code` / `rd-diff` / `rd-shell` to fenced code blocks, `rd-checklist` to GFM task lists, `rd-diagram` to a fenced block with the lang as the info string (` ```mermaid ` etc.), `rd-detail` to a raw `<details>` block, `rd-cite` / `rd-ref` to a bibliography section. Components without a natural markdown form (`rd-chart`, `rd-icon`, single-file `rd-toc`) are dropped and reported in the JSON envelope's `dropped[]` field.

## `richdoc export docx <file> [-o <path>] [--single|--multi]`

**Default (`--single`)** writes one `.docx` file with embedded images, intended for Confluence "Import Word document". Default location: `<input-stem>.docx`.

For a book, every chapter is concatenated into the one DOCX with page breaks between chapters; the shared rd-toc renders once as a "Contents" heading.

`rd-diagram` is rendered server-side via Kroki (`--diagram-endpoint <url>`, default `https://kroki.io`) and embedded as PNG. Override the server with `--diagram-endpoint <url>`; skip rendering and embed source as a code block with `--no-render-diagrams`. The diagram source is POSTed to the configured endpoint — same trust contract as `rd-diagram` in browser mode.

`-o -` writes the docx bytes to stdout (single mode only). Mapping notes:

- `rd-cols` linearises to sequential blocks (Confluence's importer doesn't preserve Word columns).
- `rd-tabs` linearises with the tab label as a Heading 3.
- `rd-detail` becomes a Heading 3 summary plus its body (collapsibility is lost).
- `rd-icon` is dropped (its `label`, if any, renders inline).
- `rd-chart` data renders as a native Word table.

## JSON envelope

Every export subcommand writes a JSON envelope to stdout (unless `-o -` is used for binary output). Fields:

```json
{
  "ok": true,
  "mode": "single|multi",
  "format": "md|docx",
  "outputs": [{"path": "/abs/path/out.md", "bytes": 12345}, ...],
  "dropped": ["rd-chart", ...],
  "diagrams_rendered": 3,
  "diagrams_failed": 0
}
```

On failure, `{"ok": false, "code": "...", "message": "..."}`.

## `richdoc export confluence <file-or-dir> [-o <path>] [...]`

Produces an **offline storage bundle** rather than calling Confluence
directly. This separates *authoring* (which is what richdoc does) from
*content management* (which is what the dedicated `confluence` skill
does). No Confluence credentials are read at this stage.

```bash
richdoc export confluence docs/                # → docs-confluence/
richdoc export confluence docs/index.html -o build/confluence-docs
```

Default output is `<stem>-confluence/` next to the input. Lint runs
first; errors block the export (pass `--no-lint` to bypass). Diagrams
and math render through Kroki the same way they do for `docx` —
override with `--diagram-endpoint URL` / `--no-render-diagrams` /
`--no-render-math`.

### Bundle layout

```
build/confluence-docs/
  manifest.json
  pages/
    <safe-name>.storage.xml         # XHTML + <ac:*> macros
  attachments/
    diag-<sha1>.png
    math-<sha1>.png
    image-<sha1>.<ext>
```

The storage XML contains two kinds of replacement tokens that the
publisher resolves at publish time:

- `@@ATTACHMENT:<prefix>:<digest>@@` → `<ac:image>` reference to an
  attachment whose filename is declared in the manifest.
- `@@RICHDOC_PAGE_URL:<page-key>@@` → absolute Confluence URL of a
  sibling page in the same bundle. The `manifest.json` records every
  token so the publisher can index substitutions without re-parsing.

### Manifest schema

Top-level `schema` is the literal string `richdoc.confluence.bundle.v1`.
Consumers should reject anything else. Pages list `key`, `source`,
`title`, `parentKey`, `storage` (relative path), `attachments[]`,
`links[]`, `dropped[]`, and `missing[]`.

### Publishing

Use the separate `confluence` skill:

```bash
confluence publish-bundle build/confluence-docs --profile work --parent-id 12345
```

The publisher is idempotent: re-running matches pages by
`(space, parent, title)`, re-uploads only changed attachments, and
resolves cross-page link tokens once page IDs are known. See
`confluence/SKILL.md`.
