# richdoc — export reference

The richdoc CLI ships exactly three export formats: markdown, HTML, and DOCX. Anything else (PDF, EPUB, etc.) is out of scope — generate from one of these three.

All three subcommands share a `--single` / `--multi` flag pair so the output shape is explicit:

- `--single` — one output file containing the whole book.
- `--multi`  — one output file per chapter, mirroring the source tree under a folder.

Defaults match the format: `md` defaults to `--multi`, `html` and `docx` default to `--single`. For a non-book input both modes still work (multi produces a folder with one file). The two flags are mutually exclusive. The JSON envelope reports the resolved `mode`.

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

## `richdoc export html <file> [-o <path>] [--single|--multi]`

**Default (`--single`)** writes one self-contained `.html` file with every relative dependency inlined as a `data:` URI. CDN dependencies (mermaid removed; KaTeX, highlight.js, Observable Plot, Lucide, PhotoSwipe) are preserved. Default location: `<input-stem>.bundle.html`. `-o -` writes to stdout.

**`--multi`** writes one HTML file per chapter into a folder, mirroring the source tree. Shared assets land in `<out>/assets/`.

`rd-diagram` is rendered server-side via Kroki (`--diagram-endpoint <url>`, default `https://kroki.io`) and embedded as PNG so the bundled HTML works offline. Skip rendering and embed source as a code block with `--no-render-diagrams`.

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
  "format": "md|html|docx",
  "outputs": [{"path": "/abs/path/out.md", "bytes": 12345}, ...],
  "dropped": ["rd-chart", ...],
  "diagrams_rendered": 3,
  "diagrams_failed": 0
}
```

On failure, `{"ok": false, "code": "...", "message": "..."}`.
