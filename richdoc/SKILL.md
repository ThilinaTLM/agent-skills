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
7. Run `richdoc lint <file>` before declaring the doc done. The lint passing is part of "done".

## CLI

Path: `./richdoc-cli/richdoc` (relative to this SKILL.md). Requires [`uv`](https://docs.astral.sh/uv/); the first call provisions the Python environment automatically.

| Command | Description |
| --- | --- |
| `richdoc new <output> [-t plan\|research\|comparison]` | Scaffold a new `.html` from a template. |
| `richdoc init [dir]` | Copy `richdoc.css` and `richdoc.js` into a directory. |
| `richdoc lint <file>` | Validate a `.html` file against the rd-* schema. |
| `richdoc components [--tag <name>]` | Print the vocabulary from the live schema. |

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
```

`richdoc new` writes a relative `<link href="./richdoc.css">` and `<script src="./richdoc.js" defer>`. The assets must exist next to the doc — run `richdoc init <dir>` once in that directory.

## Tag reference

All custom tags use the `rd-` prefix. Required attributes are marked **bold**. Run `richdoc components` to print the JSON spec from the live schema.

### Structure

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-page>` | `theme?` (`editorial-warm`), `mode?` (`light\|dark\|auto`) | Outer container. Exactly one per doc, directly under `<body>`. |
| `<rd-section>` | `title?`, `id?` | Titled section with eyebrow numeral. Title renders as `<h2>`. |
| `<rd-cols>` | `n?` (`2\|3\|4`), `template?` (CSS grid-template-columns, e.g. `"2fr 1fr"`) | Responsive grid. Use `n` for equal columns, `template` for asymmetric. Collapses to one column under ~720px. |
| `<rd-card>` | `title?`, `accent?` (`info\|success\|warn\|danger\|muted`) | Bordered block. Accent value also renders as a kicker label. |

### Information blocks

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-callout>` | **`type`** (`info\|success\|warn\|danger\|note`), `title?` | Aside with Lucide icon and colored left rule. |
| `<rd-kv>` | — | Magazine-style spec block. Children must be `<rd-row>`. |
| `<rd-row>` | **`key`** | Inside `<rd-kv>` only. Value is the element's content. |
| `<rd-badge>` | `variant?` (`info\|success\|warn\|danger\|muted`) | Inline status tag with coloured dot. |
| `<rd-stat>` | **`value`**, `label?`, `trend?` (`up\|down\|flat`), `delta?`, `tone?` (`positive\|negative\|neutral`) | Big-number dashboard tile, Fraunces display at opsz 144. |
| `<rd-quote>` | `author?`, `cite?`, `source-url?` | Pull-quote with oversized opening glyph. |
| `<rd-sidenote>` | `mark?` | Inline marginalia, auto-numbered. Renders inline-italic next to its marker on every viewport. |
| `<rd-defs>` | `title?` | Definition list. Children must be `<rd-def>`. |
| `<rd-def>` | **`term`** | One term/definition. Inside `<rd-defs>` only. |

### Comparison and code

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-compare>` | **`headers`** (comma-separated) | Hairline decision matrix. Children must be `<rd-row-cells>`. |
| `<rd-row-cells>` | **`label`** | One row in `<rd-compare>`. Children must be `<rd-cell>`. |
| `<rd-cell>` | `tone?` (`positive\|negative\|neutral`) | One cell with optional tone-coloured dot. |
| `<rd-code>` | `lang?`, `title?`, `line-numbers?`, `highlight?` (e.g. `"3,7-9"`), `start?` | Syntax-highlighted code block via highlight.js (lazy CDN load). Themed against the editorial palette. |
| `<rd-diff>` | `lang?`, `title?`, `line-numbers?` | Unified-diff with `+`/`-` lines coloured. If `lang` is set, line bodies are syntax-highlighted. |
| `<rd-math>` | `display?` (`block\|inline`) | KaTeX-rendered math, lazy-loaded from CDN. |
| `<rd-figure>` | `caption?` | Centred media with italic Fraunces caption. |

### Sequenced and interactive

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-tabs>` | — | Tabbed content. Children must be `<rd-tab>`. |
| `<rd-tab>` | **`label`**, `active?` | One pane. First tab is active unless one has `active`. |
| `<rd-timeline>` | — | Vertical timeline with dotted rule. Children must be `<rd-event>`. |
| `<rd-event>` | **`date`**, `title?` | One event with hollow-circle marker. |
| `<rd-detail>` | **`summary`**, `open?` | Hairline-only collapsible. Native `<details>`; works without JS. |
| `<rd-checklist>` | — | Hairline-separated task list. Children must be `<rd-task>`. |
| `<rd-task>` | `done?`, `assignee?`, `due?` | One item with checkbox and optional metadata. |
| `<rd-mermaid>` | — | Lazy-loads mermaid from CDN; renders the diagram from text content. |
| `<rd-toc>` | `levels?` (default `"2,3"`), `title?` (default `"On this page"`) | Auto-generated TOC from `<h2>`/`<h3>` inside the parent `<rd-page>`. |
| `<rd-icon>` | **`name`** (enum), `size?` (`sm\|md\|lg`), `label?` | Inline SVG from vendored Lucide subset. Run `richdoc components --tag rd-icon` for the available names. |

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

- **`plan`** — title, problem callout, goals, steps timeline, risks, open questions, acceptance criteria.
- **`research`** — summary callout, TOC, findings, comparison matrix, recommendation, references.
- **`comparison`** — context, criteria, comparison matrix, trade-offs grid, recommendation.

Scaffold with `richdoc new <output> --template <name>`.

## Limitations

- **JS required** for tabs, mermaid, math, syntax highlighting, TOC, and the copy button. Other components render with CSS alone.
- **Internet required on first render** of `rd-mermaid`, `rd-math`, and any `rd-code` with `lang` set (mermaid / KaTeX / highlight.js load from CDN). Each falls back to raw source if offline.
- **One document per file.** No multi-page nav.
- **Browser-only consumer.** Use markdown if the doc must render on GitHub, in plaintext email, or in a CLI pager.
