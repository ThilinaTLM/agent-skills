---
name: richdoc
description: This skill should be used when the user asks to "write a research report", "create a plan document for review", "produce a polished design doc", "draft a comparison sheet", "generate a richdoc", "make a one-pager", "write a status report", "produce an executive summary", "create a decision document", "build a dashboard page", or any other rich HTML deliverable intended for human review in a browser. Authors plain .html files using a small fixed vocabulary of rd-* web components for layout and rich blocks. Includes a CLI for scaffolding, asset installation, schema introspection, and validation.
---

# richdoc

richdoc is for **AI-authored, human-read HTML documents**. The agent writes a normal `.html` file using a closed vocabulary of `rd-*` web components. Two shipped assets (`richdoc.css`, `richdoc.js`) give every component its editorial look and behavior. No build step on the consumer side; the file opens in any browser, with or without a server.

## When to use richdoc

Plans, research reports, design docs, status one-pagers, decision memos, comparisons, postmortems, dashboards — anything where the reader is a person in a browser. Use markdown only when the renderer might be anything else (GitHub, chat, CLI). Anywhere else, richdoc is the better default.

## Authoring rules

When writing a richdoc, the agent **must**:

1. Produce a complete HTML5 document with exactly one `<rd-page>` directly inside `<body>`. Link `richdoc.css` and `richdoc.js` from `<head>`.
2. Use **only** the `rd-*` tags listed below. Inventing new ones causes lint errors and renders as empty boxes.
3. For prose, use plain semantic HTML — `<p>`, `<ul>`, `<ol>`, `<li>`, `<a>`, `<strong>`, `<em>`, `<code>`, `<pre>`, `<h1>`–`<h6>`, `<blockquote>`, `<hr>`, `<img>`, `<table>`. These are styled automatically; do not wrap every paragraph in a component.
4. Prefer `<rd-callout>` over bold-italic emphasis for asides longer than a few words.
5. Use `<rd-cols>` for genuinely parallel content (cards, stats, comparisons). Do not use it to force a two-column paragraph layout — text becomes unreadable.
6. Put code in `<rd-code lang="…">`, diffs in `<rd-diff lang="…">`, math in `<rd-math>`. Don't fall back to `<pre>`.
7. **Never self-close custom elements.** Write `<rd-foo ...></rd-foo>`, not `<rd-foo ... />`. HTML5 ignores the closing slash on non-void custom elements — the tag stays open and silently absorbs every following sibling as a child. `richdoc lint` catches this as `self-closing-custom-element`.
8. Run `richdoc lint <file>` before declaring the doc done. The lint passing is part of "done".

## CLI

Path: `./richdoc-cli/richdoc` (relative to this SKILL.md). Requires [`uv`](https://docs.astral.sh/uv/); the first call provisions the Python environment automatically.

| Command | Description |
| --- | --- |
| `richdoc new <output> [-t plan\|research\|comparison]` | Scaffold a new `.html` from a template. |
| `richdoc init [dir]` | Copy `richdoc.css` and `richdoc.js` into a directory. |
| `richdoc update [dir] [--apply]` | Find existing doc folders with stale shipped assets and (optionally) refresh them. |
| `richdoc lint <file>` | Validate a `.html` file against the rd-* schema. |
| `richdoc components [--tag <name>]` | Print the vocabulary from the live schema. |
| `richdoc export md <file> [-o out_dir]` | Export to a folder of markdown files (book chapters auto-detected) with a shared `assets/` directory. |
| `richdoc export html <file> [-o out.html]` | Export to a single self-contained `.html` file (relative deps inlined as `data:` URIs, CDN deps preserved). |
| `richdoc export docx <file> [-o out.docx]` | Export to a single `.docx` file with embedded images, intended for Confluence “Import Word document”. |

### Typical authoring flow

```bash
# Drop the assets into your docs directory once.
mkdir -p docs && richdoc init docs

# Scaffold a new document from a template.
richdoc new docs/auth-plan.html -t plan

# Edit docs/auth-plan.html.

# Validate before sharing.
richdoc lint docs/auth-plan.html

# Open in any browser. No server needed.
xdg-open docs/auth-plan.html

# After bumping the richdoc skill, find any stale asset copies in the repo
# (report-only by default; recursive; skips node_modules, .venv, dist, ...).
richdoc update .            # report
richdoc update . --apply    # refresh stale folders

# Convert to a folder of markdown files (one per chapter for books).
richdoc export md docs/auth-plan.html

# Produce a self-contained HTML you can share as a single file.
richdoc export html docs/auth-plan.html

# Produce a .docx for Confluence import.
richdoc export docx docs/auth-plan.html
```

## Export

The richdoc CLI ships exactly three export formats. Anything else (PDF, EPUB, etc.) is out of scope — generate from one of these three.

All three subcommands share a `--single` / `--multi` flag pair so the output shape is explicit:

- `--single` — one output file containing the whole book.
- `--multi`  — one output file per chapter, mirroring the source tree under a folder.

Defaults match the format: `md` defaults to `--multi`, `html` and `docx` default to `--single`. For a non-book input both modes still work (multi produces a folder with one file). The two flags are mutually exclusive. The JSON envelope reports the resolved `mode`.

`--no-book` overrides auto-detection and renders only the entry file, regardless of the mode flag.

### `richdoc export md <file> [-o <path>] [--single|--multi]`

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

Assets are shared across the whole book in one `assets/` at the root.

**`--single`** writes one combined `.md`. Default location: `<input-stem>.md`. The combined file has a single `# Book title` H1, a `## Contents` block linking each chapter, then every chapter's body with all headings demoted by one level (so each chapter sits at `##`). The shared `<rd-toc>` in each chapter is stripped (the `## Contents` block already covers it). Page-rule `---` separators between chapters. Assets land in a single `assets/` directory next to the output `.md`.

Relative image references are copied into `assets/` automatically. Remote (http/https) image URLs are left as-is by default; pass `--include-remote-images` to fetch and copy them too.

Every `rd-*` component maps to the closest markdown idiom: callouts to GFM admonitions (`> [!NOTE]`), `rd-compare` / `rd-rubric` / `rd-roadmap` / `rd-api` to tables, `rd-code` / `rd-diff` / `rd-shell` to fenced code blocks, `rd-checklist` to GFM task lists, `rd-footnote` and `rd-cite` to footnotes, `rd-detail` to a raw `<details>` block. Components without a natural markdown form (`rd-chart`, `rd-icon`, single-file `rd-toc`) are dropped and reported in the JSON envelope's `dropped[]` field.

### `richdoc export html <file> [-o <path>] [--single|--multi]`

**Default (`--single`)** writes one self-contained `.html` file. Default name: `<input-stem>.bundle.html`. Inlines `richdoc.css`, `richdoc.js`, and every relative-path image / font / media reference as inline `<style>` / `<script>` / `data:` URIs. Absolute URLs (Google Fonts, jsDelivr) stay as-is — the recipient is expected to have internet when opening the file. Pass `-o -` to write to stdout (the JSON envelope is suppressed in that mode).

**`--multi`** writes a folder of self-contained bundles, one per chapter, mirroring the source tree. Default location: `<input-stem>-html/`. Each chapter is inlined against its own directory so intra-book hrefs (`<a href="./02-habitat.html">`) still resolve against the mirrored layout.

### `richdoc export docx <file> [-o <path>] [--single|--multi]`

**Default (`--single`)** writes one `.docx`. Default name: `<stem>.docx`. Designed for Confluence's “Import Word document”: headings become Heading 1–6, lists become Word bullet / number lists, tables become Table Grid, and **every image is embedded inside the docx package** (relative AND remote) so Confluence renders them on import without further attachment uploads.

For a book, every chapter is concatenated into the one DOCX with page breaks between chapters; the shared rd-toc renders once as a "Contents" heading.

**`--multi`** writes one `.docx` per chapter under a folder mirroring the source tree. Each chapter is fully self-sufficient (assets embedded in every file).

`rd-mermaid` and `rd-plantuml` are rendered server-side via Kroki (`https://kroki.io` by default) and embedded as PNG. Override the server with `--diagram-endpoint <url>`; skip rendering and embed source as a code block with `--no-render-diagrams`. The diagram source is POSTed to the configured endpoint — same trust contract as `rd-plantuml` in browser mode.

`-o -` writes the docx bytes to stdout (single mode only). Mapping notes: `rd-cols` linearises to sequential blocks (Confluence's importer doesn't preserve Word columns); `rd-tabs` linearises with the tab label as a Heading 3; `rd-detail` becomes a Heading 3 summary plus its body (collapsibility is lost); `rd-icon` is dropped (its `label`, if any, renders inline); `rd-chart` data renders as a native Word table.

A network-isolated host can't produce a complete docx — image fetches and diagram renders will fail and surface as `missing[]` and `diagrams_failed` in the JSON envelope.

`richdoc new` writes a relative `<link href="./richdoc.css">` and `<script src="./richdoc.js" defer>`. The assets must exist next to the doc — run `richdoc init <dir>` once in that directory.

## Tag reference

All custom tags use the `rd-` prefix. Required attributes are marked **bold**. Run `richdoc components` to print the JSON spec from the live schema.

### Structure

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-page>` | `theme?` (`editorial-warm`), `mode?` (`light\|dark\|auto`) | Outer container. Exactly one per doc, directly under `<body>`. |
| `<rd-hero>` | **`title`**, `eyebrow?`, `lede?`, `meta?` | Magazine-style top-of-page header. Replaces the ad-hoc `<h1>` + `<rd-kv>` opener. Children render as an "extras" strip below the meta line. |
| `<rd-banner>` | **`type`** (`draft\|frozen\|archived\|confidential\|info`), `message?` | Thin doc-status ribbon. Sits at the top of `<rd-page>`. Default message comes from the type; element content overrides it. |
| `<rd-section>` | `title?`, `id?` | Titled section with eyebrow numeral. Title renders as `<h2>`. |
| `<rd-cols>` | `n?` (`2\|3\|4`), `template?` (CSS grid-template-columns, e.g. `"2fr 1fr"`) | Responsive grid. Use `n` for equal columns, `template` for asymmetric. Collapses to one column under ~720px. |
| `<rd-card>` | `title?`, `accent?` (`info\|success\|warn\|danger\|muted`) | Bordered block. Accent value also renders as a kicker label. |

### Information blocks

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-callout>` | **`type`** (`info\|success\|warn\|danger\|note\|tldr`), `title?` | Aside with Lucide icon and colored left rule. `type="tldr"` renders as a full-width summary band with no icon (default title `"TL;DR"`) — use it as the first block after `<rd-hero>`. |
| `<rd-kv>` | `title?`, `layout?` (`inline\|stacked`) | Magazine-style spec block. Children must be `<rd-row>`. `layout="stacked"` plus optional `title` renders a glossary / definition list — terms in Fraunces italic over the value body, hairline separators. |
| `<rd-row>` | **`key`** | Inside `<rd-kv>` only. Value is the element's content. |
| `<rd-badge>` | `variant?` (`info\|success\|warn\|danger\|muted`) | Inline status tag with coloured dot. |
| `<rd-stat>` | **`value`**, `label?`, `trend?` (`up\|down\|flat`), `delta?`, `tone?` (`positive\|negative\|neutral`) | Big-number dashboard tile, Fraunces display at opsz 144. Children render as a small slot below the number (typically an `<rd-chart variant="sparkline">`). |
| `<rd-progress>` | **`value`** (`0..1`, `N%`, or `N/M`), `label?`, `tone?` (`positive\|negative\|neutral`) | Linear progress / capacity bar. Fill count-up animates on entry. |
| `<rd-update>` | **`date`**, `kind?` (`release\|change\|note`), `author?`, `title?` | Dated reverse-chron entry for changelogs, release notes, status reports. |
| `<rd-quote>` | `author?`, `cite?`, `source-url?` | Pull-quote with oversized opening glyph. |
| `<rd-footnote>` | `mark?` | Inline superscript marker that links to a numbered entry collected in an auto-generated `<rd-footnotes>` block at the foot of the enclosing `<rd-page>`. Hover or focus the marker for a rich preview of the note; click to scroll to the entry. Each entry includes a back-link to its marker. |
| `<rd-swatch>` | **`kind`** (`color\|type\|space\|radius\|shadow`), **`name`**, **`value`**, `note?` | Design-token chip. Preview surface on the left, name + value on the right. |

### Comparison and code

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-compare>` | **`headers`** (comma-separated) | Hairline decision matrix. Children must be `<rd-row-cells>`. |
| `<rd-row-cells>` | **`label`** | One row in `<rd-compare>`. Children must be `<rd-cell>`. |
| `<rd-cell>` | `tone?` (`positive\|negative\|neutral`) | One cell with optional tone-coloured dot. |
| `<rd-rubric>` | **`options`** (comma-separated), `scale?` (default `5`), `title?` | Weighted scoring grid with automatic totals. Children must be `<rd-criterion>`. The highest-total column highlights. |
| `<rd-criterion>` | **`label`**, `weight?` (default `1`) | One row in `<rd-rubric>`. Children must be `<rd-score>` in the order of the parent's `options`. |
| `<rd-score>` | **`value`** (0..scale), `note?` | One cell in `<rd-criterion>`. |
| `<rd-code>` | `lang?`, `title?`, `line-numbers?`, `highlight?` (e.g. `"3,7-9"`), `start?` | Syntax-highlighted code block via highlight.js (lazy CDN load). Themed against the editorial palette. |
| `<rd-diff>` | `lang?`, `title?`, `line-numbers?` | Unified-diff with `+`/`-` lines coloured. If `lang` is set, line bodies are syntax-highlighted. |
| `<rd-shell>` | `title?` | Terminal session block. Children must be `<rd-prompt>` and/or `<rd-output>`. Distinct from `<rd-code>` — no highlighting, no copy button. |
| `<rd-prompt>` | `cwd?`, `user?` | Terminal command line. Renders with a `$` glyph and optional dim `cwd` prefix. Inside `<rd-shell>` only. |
| `<rd-output>` | `tone?` (`positive\|negative\|neutral`) | Terminal output block. Whitespace is preserved. Inside `<rd-shell>` only. |
| `<rd-math>` | `display?` (`block\|inline`) | KaTeX-rendered math, lazy-loaded from CDN. |
| `<rd-figure>` | `caption?` | Centred media with italic Fraunces caption. |
| `<rd-chart>` | `variant?` (`chart\|sparkline`), `kind?` (`bar\|line\|area\|donut\|scatter\|heatmap`), `data?`, `format?` (`json\|csv`), `x?`, `y?`, `series?`, `labels?`, `title?`, `caption?`, `height?`, `width?`, `legend?`, `color?`, `endpoint?` | SVG chart via Observable Plot (lazy CDN). Data lives in the `data` attribute (JSON or compact `1,2,3` list) or as the element's text content. Falls back to a table if Plot can't load. `variant="sparkline"` strips title / caption / legend / body wrapper and renders inline — tune with `width`, `height`, `color`, `endpoint`. |
| `<rd-gallery>` | `cols?` (`2\|3\|4`, default `3`), `title?` | Image grid. Click opens a PhotoSwipe lightbox. Children must be `<rd-shot>`. With no JS / no network the grid links open the source image in a new tab. |
| `<rd-shot>` | **`src`**, **`alt`**, `caption?`, `width?`, `height?` | One image. Inside `<rd-gallery>` only. Width/height are auto-detected from the loaded image but can be set explicitly to avoid the probe. |
| `<rd-embed>` | **`src`**, **`title`**, `aspect?` (default `"16:9"`), `caption?` | YouTube / Vimeo / generic iframe wrapper. YouTube and Vimeo URLs use lite-youtube and lite-vimeo web components for fast initial paint; other URLs render as a sandboxed iframe. |

### Sequenced and interactive

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-tabs>` | — | Tabbed content. Children must be `<rd-tab>`. |
| `<rd-tab>` | **`label`**, `active?` | One pane. First tab is active unless one has `active`. |
| `<rd-timeline>` | — | Vertical timeline with dotted rule. Children must be `<rd-event>`. |
| `<rd-event>` | **`date`**, `title?` | One event with hollow-circle marker. |
| `<rd-steps>` | — | Numbered procedural steps for runbooks, onboarding flows. Children must be `<rd-step>`. |
| `<rd-step>` | **`title`**, `done?` | One step with display-Fraunces numeral and rich body. Inside `<rd-steps>` only. |
| `<rd-detail>` | **`summary`**, `variant?` (`panel\|hairline\|question\|reveal`), `open?` | Collapsible disclosure on native `<details>`; works without JS. `panel` (default) is bordered with a header strip; `hairline` is a bracketed open/close row; `question` renders the summary in display Fraunces (use for Q/A blocks); `reveal` swaps the chevron for an eye glyph and toggles the label to `"Hide"` while open (use for spoilers). |
| `<rd-tree>` | `title?` | Collapsible hierarchical tree on native `<details>`. Children must be `<rd-node>`. |
| `<rd-node>` | **`label`**, `open?`, `icon?` | One tree node. Nested `<rd-node>` children become the disclosure body; leaves render as a row with no chevron. |
| `<rd-checklist>` | — | Hairline-separated task list. Children must be `<rd-task>`. |
| `<rd-task>` | `done?`, `assignee?`, `due?` | One item with checkbox and optional metadata. |
| `<rd-mermaid>` | — | Lazy-loads mermaid from CDN; renders the diagram from text content. |
| `<rd-plantuml>` | `endpoint?` (default `https://kroki.io/plantuml/svg`), `theme?` (any PlantUML theme name, or `none`) | Renders PlantUML from text content by encoding the source and fetching SVG from a PlantUML-compatible server. Defaults to [Kroki](https://kroki.io) — same backend `richdoc-cli` uses for diagram pre-rendering, so browser and export output stay consistent. **The source is sent to that server** — set `endpoint` to a self-hosted Kroki or PlantUML instance for sensitive diagrams. Auto-injects `!theme cyborg-outline` when the doc is in dark mode so the diagram matches the surrounding palette; override with `theme="<name>"` (e.g. `superhero`, `reddress-darkblue`, `plain`) or disable with `theme="none"`. An author-written `!theme` line in the source is always respected. Falls back to a code block if the server is unreachable. |
| `<rd-toc>` | `levels?` (default `"2,3"`), `title?` | Auto-generated TOC. Default mode walks `<h2>`/`<h3>` inside the parent `<rd-page>`. If the element contains `<rd-chapter>` children, it switches to **book mode**: renders a cross-file chapter sidebar, auto-marks the active chapter by URL match, expands in-page headings inline beneath it, and auto-injects prev/next bands at the top and bottom of `<rd-page>`. See [Multi-file documentation](#multi-file-documentation). |
| `<rd-chapter>` | `href?` | One entry in a book-mode `<rd-toc>`. Title is the element's text content. With `href` it's a link; without `href` it's a non-clickable group header. Nested `<rd-chapter>` becomes a sub-tree. Inside `<rd-toc>` or another `<rd-chapter>` only. |
| `<rd-icon>` | **`name`** (enum), `size?` (`sm\|md\|lg`), `label?` | Inline SVG from the full Lucide library at a pinned version (~1,900 names). Every glyph is lazy-loaded from jsDelivr on first reference and cached; framework chrome icons are prewarmed at boot so callouts / checklists / banners never flash. See [ICONS.md](./ICONS.md) for the full name list. Offline or on a failed fetch the element renders an empty slot of the right size and gets `data-rd-icon-missing`. |
| `<rd-tooltip>` | **`term`** (text), `placement?` (`auto\|top\|bottom`) | Inline definition popup. The `term` renders with a dotted underline; the children render as a rich tooltip body on hover, focus, or tap. |

### Decision and planning

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-decision>` | **`status`** (`proposed\|accepted\|superseded\|rejected`), `id?`, `date?`, `deciders?`, `title?` | ADR-style decision record header + rationale block. Status drives the left rule colour and the status pill. |
| `<rd-pros-cons>` | `pros-title?`, `cons-title?` | Two-column ✓/✗ evaluation grid. Children must be `<rd-pro>` and/or `<rd-con>`. Distinct from `<rd-compare>` (a matrix). |
| `<rd-pro>` | — | One pro point. Inside `<rd-pros-cons>` only. |
| `<rd-con>` | — | One con point. Inside `<rd-pros-cons>` only. |
| `<rd-roadmap>` | **`start`** (ISO date), **`end`** (ISO date), `unit?` (`day\|week\|month\|quarter`), `title?` | Themed CSS gantt — no external library, no horizontal scrollbars. Bars are positioned by percentage within each lane, a discreet “today” marker is drawn when the current date falls inside the window, and items take optional `progress` / `tone`. Children must be `<rd-lane>`. |
| `<rd-lane>` | **`name`** | One workstream lane. Children must be `<rd-item>`. Inside `<rd-roadmap>` only. |
| `<rd-item>` | **`start`** (ISO), **`end`** (ISO), **`label`**, `tone?` (`positive\|negative\|neutral`), `progress?` (`0..1`) | One bar in `<rd-lane>`. |

### Reference

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-api>` | **`method`** (`GET\|POST\|PUT\|PATCH\|DELETE\|HEAD\|OPTIONS`), **`path`**, `auth?`, `title?` | Single-endpoint API reference. Method pill coloured per verb. Children must be `<rd-param>` and/or `<rd-response>`. |
| `<rd-param>` | **`name`**, `in?` (`query\|path\|body\|header`, default `query`), `required?`, `type?`, `default?` | One parameter. Body content describes the parameter. Inside `<rd-api>` only. |
| `<rd-response>` | **`status`**, `type?` | One response. Body content describes the payload. Status pill tints itself by 2xx/4xx class. Inside `<rd-api>` only. |
| `<rd-references>` | `title?` (default `"References"`) | Optional explicit placement for the auto-generated bibliography. If omitted, the bibliography is appended to the foot of the enclosing `<rd-page>` after `<rd-footnotes>`. |
| `<rd-ref>` | **`key`**, `author?`, `title?`, `url?`, `date?`, `publisher?` | One bibliography entry. Anywhere in the doc; rendered only inside the bibliography. Element body content (if any) appears as a note. |
| `<rd-cite>` | **`key`** | Inline citation marker. Renders as `[N]` with a tooltip preview of the entry and a click-jump to the bibliography. Numbered in document order; uncited entries appear at the end of the bibliography. |

## Minimal example

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>My plan</title>
  <link rel="stylesheet" href="./richdoc.css">
  <script src="./richdoc.js" defer></script>
</head>
<body>
<rd-page>
  <h1>My plan</h1>

  <rd-kv>
    <rd-row key="Status"><rd-badge variant="info">draft</rd-badge></rd-row>
    <rd-row key="Owner">platform team</rd-row>
  </rd-kv>

  <rd-callout type="info" title="Problem">
    One or two sentences on what we're solving.
  </rd-callout>

  <rd-section title="Approach">
    <p>Plain prose, lists, and links work as usual.</p>
  </rd-section>

  <rd-section title="Trade-offs">
    <rd-cols n="2">
      <rd-card title="Option A" accent="success">Pros, cons.</rd-card>
      <rd-card title="Option B" accent="warn">Pros, cons.</rd-card>
    </rd-cols>
  </rd-section>
</rd-page>
</body>
</html>
```

`examples/showcase.html` exercises every component. `examples/status-onepager.html` shows a realistic dashboard.

## Templates

- **`plan`** — hero, TL;DR callout, problem callout, goals, pros/cons, numbered steps, risks, open questions as `<rd-detail variant="question">`, acceptance criteria.
- **`research`** — hero, TL;DR callout, TOC, findings with inline citations, scored rubric, recommendation as a decision record, references.
- **`comparison`** — hero, TL;DR callout, context, scored rubric, trade-offs grid with pros/cons cards, decision record.
- **`onepager`** — hero, TL;DR callout, stat tiles with sparkline charts, progress bars, line chart, recent updates feed, risks.
- **`adr`** — hero, decision header, context, considered options, decision, consequences, references.
- **`runbook`** — hero, TL;DR callout, prerequisites checklist, numbered steps with terminal sessions, failure modes as `<rd-detail variant="question">`, escalation.
- **`book-index`** — entry page for a multi-file book: shared `<rd-toc>` chapter list, hero, TL;DR, contents tour.
- **`book-chapter`** — chapter page in a multi-file book: same shared `<rd-toc>` chapter list, hero, TL;DR, body.

Scaffold with `richdoc new <output> --template <name>`.

## Multi-file documentation

For docs that don't fit in a single file — handbooks, runbook sets, reference manuals — use **book mode**: put an `<rd-toc>` with `<rd-chapter>` children in each page. The same shared block lives in every file; `<rd-toc>` does the rest at runtime.

```html
<rd-page>
  <rd-toc title="My Handbook">
    <rd-chapter href="./index.html">Overview</rd-chapter>
    <rd-chapter href="./01-setup.html">Setup</rd-chapter>
    <rd-chapter href="./02-api.html">API reference</rd-chapter>
    <rd-chapter>Operations
      <rd-chapter href="./ops/runbook.html">Runbook</rd-chapter>
      <rd-chapter href="./ops/escalation.html">Escalation</rd-chapter>
    </rd-chapter>
  </rd-toc>

  <rd-hero title="Setup"/>
  …content…
</rd-page>
```

Implicit behaviors — do **not** write attributes for any of these:

- **Active chapter** is detected by matching `location.pathname` against each `<rd-chapter href>`. Trailing-slash paths are normalised to `index.html`.
- **In-page headings** for the active chapter are merged inline under that chapter in the sidebar (Sphinx-style). One element produces both kinds of navigation.
- **Prev / next bands** are auto-injected at the top of `<rd-page>` (after `<rd-banner>` if present) and the bottom. Order comes from the chapter tree in document order; group headers (`<rd-chapter>` with no `href`) are skipped.
- **Group headers** are non-clickable section labels. Use them to organise chapters into chapter groups.
- **Title** is the chapter's text content, not a `title=` attribute. Whitespace is collapsed.

Authoring rules for books:

1. **Copy the `<rd-toc>` block verbatim into every page** in the book. There is intentionally no build step and no cross-file fetch — the chapter list must be present in each file. Re-order chapters by editing every page (typically only a handful) or add a `richdoc book sync` helper later. The list is stable and only changes when the book's structure changes.
2. **Do not hand-write prev/next.** `<rd-toc>` injects them. Hand-written copies will collide.
3. **Use relative `href` paths** (`./foo.html`, `../bar.html`). `richdoc lint` checks that each relative href resolves to a file on disk. Absolute URLs are allowed (external appendix) but the active-chapter / prev-next math treats them as ordinary entries.
4. **`<rd-toc title="…">` is the book title.** It shows as the rail's eyebrow and the narrow-mode bar label. The chapter title is the bar's current-item label.

See `examples/book/` for a multi-file walkthrough with subdirectories.

## Motion

richdoc has a small, consistent motion vocabulary driven by tokens in `richdoc.css`:

- **Page-enter cascade** — the first ~8 direct children of `<rd-page>` fade and lift in on load (~180 ms with a 20 ms stagger).
- **Viewport-entry reveal** — `<rd-stat>`, `<rd-card>`, `<rd-callout>`, `<rd-figure>`, `<rd-quote>`, `<rd-event>`, `<rd-step>`, `<rd-update>`, `<rd-progress>`, `<rd-chart>`, and `<rd-roadmap>` reveal as they scroll into view.
- **`<rd-stat>` count-up** — numeric values animate from zero on entry. Non-numeric values (`"complete"`, `"42 days"`) render immediately.
- **`<rd-progress>` fill** — the bar interpolates from 0 to its target width on entry, mirroring the count-up easing.
- **`<rd-detail>`** — chevron (or eye glyph for `variant="reveal"`) and disclosure body height interpolate in browsers that support `interpolate-size`. Applies to every variant.
- **`<rd-tabs>`** — active underline slides between tabs.
- **`<rd-checklist>` / `<rd-step done>`** — the check icon scales in when an item is marked done.
- **`<rd-banner>`** — slides in from the top edge on first paint.
- **`<rd-callout type="warn">` / `"danger"`** — a one-shot pulse on entry. Other variants stay still.

All motion is gated on `prefers-reduced-motion: reduce` and collapses to instant transitions for users who opt out at the OS level.

## Limitations

- **JS required** for tabs, mermaid, math, syntax highlighting, charts, sparklines, roadmaps, the gallery lightbox, video embeds, citation collection, TOC, the count-up animation, the tabs underline indicator, and the copy button. Other components render with CSS alone.
- **Internet required on first render** of `rd-mermaid`, `rd-math`, any `rd-code` with `lang` set, `rd-chart` (including `variant="sparkline"`), `rd-gallery`, `rd-embed`, and any `<rd-icon>` whose glyph has not been prewarmed or previously fetched. mermaid / KaTeX / highlight.js / lucide-static / Observable Plot / d3 / PhotoSwipe / lite-youtube / lite-vimeo all load from jsDelivr. `rd-roadmap` renders entirely from local CSS/JS — no CDN. Every component degrades gracefully offline: code blocks show raw source, math shows the source, charts render their data as a table, galleries become a plain image grid, embeds become a link, and icons show an empty slot of the right size.
- **`rd-plantuml` sends source to a third-party server on every render.** Unlike `rd-mermaid` (pure-JS, renders locally after a one-time CDN load), `rd-plantuml` has no client-only renderer — every diagram is round-tripped through a PlantUML-compatible server as a URL-encoded payload. The default endpoint is `https://kroki.io/plantuml/svg` (Kroki's public service), which matches the backend `richdoc-cli` uses for diagram pre-rendering. Set the `endpoint` attribute to a self-hosted Kroki or `plantuml/plantuml-server` instance for confidential content. Requires `CompressionStream` (Chrome 90+, Firefox 113+, Safari 16.4+); falls back to a code block on older engines.
- **Multi-file books duplicate the chapter list.** Each chapter file contains the same `<rd-toc>` block. This is intentional — the format must work without a CLI build step and without runtime cross-file fetch (modern browsers block `fetch()` from `file://`). Re-ordering chapters means editing every page; lint catches stale `href`s.
- **Browser-only consumer.** Use markdown if the doc must render on GitHub, in plaintext email, or in a CLI pager.
