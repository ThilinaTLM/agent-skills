---
name: richdoc
description: This skill should be used when the user asks to "write a research report", "create a plan document for review", "produce a polished design doc", "draft a comparison sheet", "generate a richdoc", "make a one-pager", "write a status report", "produce an executive summary", "create a decision document", "build a dashboard page", or any other rich HTML deliverable intended for human review in a browser. Authors plain .html files using a small fixed vocabulary of rd-* web components for layout and rich blocks. Includes a CLI for scaffolding, asset installation, schema introspection, and validation.
---

# richdoc

richdoc is a small framework for **AI-authored, human-read HTML documents**. The agent writes a normal `.html` file using a closed vocabulary of `rd-*` web components. Two shipped assets (`richdoc.css`, `richdoc.js`) give every component its look and behavior. No build step on the consumer side. The file opens in any browser, with or without a server.

## When to use richdoc

Use richdoc whenever an agent produces a document that benefits from real structure — plans for stakeholders, research reports, status one-pagers, decision memos, comparison docs, postmortems, dashboards. The constrained vocabulary plus the linter make agent output reliable; the rich components make the result something humans actually want to read.

Markdown still has its place: when a doc must render on GitHub, in chat, or in any plain-text context, write markdown. **For anything else** — anywhere the consumer is a browser — richdoc is the better default.

## Why HTML, not markdown

Markdown is optimized for situations where the renderer might be anything (a code review tool, a CLI pager, a wiki, a chat client). That generality is also its ceiling: there is no portable way to express two columns, a status pill, a comparison matrix, a collapsible appendix, or a tabbed sample. Agents end up bending markdown with bold-italic stacks, nested blockquotes, and ASCII tables that get worse the more information they carry.

richdoc takes the opposite trade. It assumes the consumer is a browser (true for ~every doc a stakeholder will read in 2026) and gives the agent a small set of layout components that map onto how humans actually scan documents:

- **Predictable vocabulary.** ~24 tags. The agent doesn't reinvent its rendering language each session. A doc written today still renders the same way next year because the vocabulary is closed.
- **Validated at write time.** `richdoc lint` catches missing required attributes, unknown tags, wrong parents, and bad enum values *before* the doc reaches a human. Markdown has nothing equivalent.
- **Layout is the agent's tool, not its burden.** The agent writes `<rd-cols n="3">` or `<rd-stat label="…" value="…">` — it does not invent CSS, choose colors, or fight with ASCII art.
- **Richer reading experience.** Callouts, collapsible details, attributed quotes, dashboard tiles, syntax-highlighted code with a copy button, mermaid diagrams. None of these are markdown extensions; all of them ship in the core.
- **Single-file, server-free.** One `.html` file plus two assets. Open it from `file://`, email it, save it to a wiki. Works the same everywhere.

This is also why the vocabulary is small. Every additional tag is a thing the agent must remember and humans must learn to read. We resist feature creep aggressively — see `AUTHORING.md` for the bar a new component must clear.

## Architecture in one paragraph

`richdoc.js` is a classic (non-module) script that registers every `rd-*` custom element via `customElements.define`. `richdoc.css` provides the tokens, base typography, and per-component styles. The agent writes a normal HTML file that links both from `<head>`. When the browser parses the doc, the registered components upgrade their tags and inject any chrome they need (headers, copy buttons, computed TOCs, mermaid SVG). The source HTML stays human-readable; the linter can be run without a runtime.

## Files

```
richdoc/
├── SKILL.md                      # this file
├── AUTHORING.md                  # how to add or change a component
├── src/                          # framework source (CSS + TS + schema, one folder per tag)
├── build.ts                      # produces the assets below from src/
├── assets/                       # shipped, committed bundle
│   ├── richdoc.css
│   ├── richdoc.js
│   ├── schema.json               # CLI loads this for `richdoc lint`
│   └── version.txt               # bundle hash + build timestamp
├── templates/                    # plan.html, research.html, comparison.html
├── examples/                     # showcase.html, status-onepager.html
└── richdoc-cli/                  # CLI: new, init, lint, build, components
```

The CLI reads `assets/schema.json` — there is no second copy of the vocabulary in the CLI source.

## CLI

- Path: `./richdoc-cli/richdoc` (relative to this SKILL.md). Requires [`uv`](https://docs.astral.sh/uv/); the first call provisions the Python environment automatically.
- Output is JSON only — designed for AI agents. All commands return `{ ok: true, ... }` or `{ ok: false, error, code, hint }`.
- Run `richdoc --help` or `richdoc <command> --help` for current flags.

| Command | Description |
| --- | --- |
| `richdoc new <output> [-t plan\|research\|comparison]` | Scaffold a new `.html` from a template. |
| `richdoc init [dir]` | Copy `richdoc.css` and `richdoc.js` into a directory. |
| `richdoc lint <file>` | Validate a `.html` file against the rd-* schema. |
| `richdoc components [--tag <name>]` | List the vocabulary (always in sync with the schema). |

Framework asset rebuilds (regenerating `richdoc.js`/`richdoc.css`/`schema.json` from `src/`) are not part of the CLI; run `bun run build` directly from the `richdoc/` root. That's a framework-developer task, not an authoring one.

### Typical authoring flow

```bash
# Drop the assets into your docs directory once.
mkdir -p docs && richdoc init docs

# Scaffold a new document from a template.
richdoc new docs/auth-plan.html -t plan

# Edit docs/auth-plan.html — fill in the TODOs.

# Validate before sharing.
richdoc lint docs/auth-plan.html

# Open in any browser. No server needed.
xdg-open docs/auth-plan.html
```

`richdoc new` writes a relative `<link href="./richdoc.css">` and `<script src="./richdoc.js" defer>`. The assets must exist next to the doc — run `richdoc init <dir>` once in that directory.

## Authoring rules

When writing a richdoc, the agent **must**:

1. Produce a complete HTML5 document with exactly one `<rd-page>` directly inside `<body>`. Link `richdoc.css` and `richdoc.js` from `<head>`.
2. Use **only** the `rd-*` tags listed in the reference below. Inventing new ones causes lint errors and renders as empty boxes.
3. For prose, use plain semantic HTML — `<p>`, `<ul>`, `<ol>`, `<li>`, `<a>`, `<strong>`, `<em>`, `<code>`, `<pre>`, `<h1>`–`<h6>`, `<blockquote>`, `<hr>`, `<img>`, `<table>`. These are styled automatically; do not wrap every paragraph in a component.
4. Prefer `<rd-callout>` over bold-italic emphasis for asides longer than a few words.
5. Use `<rd-cols>` for genuinely parallel content (cards, stats, comparisons). Do not use it to force a two-column paragraph layout — text becomes unreadable.
6. Put code in `<rd-code lang="…">`, not raw `<pre><code>` — you lose the header bar and copy button.
7. Run `richdoc lint <file>` before declaring the doc done. The lint passing is part of "done".

## Tag reference

All custom tags use the `rd-` prefix. Required attributes are marked **bold**. Run `richdoc components` to print the JSON spec from the live schema.

### Structure

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-page>` | `theme?` (`editorial-warm`), `mode?` (`light\|dark\|auto`) | Outer container. Exactly one per doc, directly under `<body>`. `theme` picks the palette family; `mode` picks light/dark. Both default to inherited / auto. |
| `<rd-section>` | `title?`, `id?` | Titled section with vertical rhythm. Title renders as `<h2>`. |
| `<rd-cols>` | **`n`** (`2\|3\|4`) | Responsive grid. Collapses to one column under ~720px. |
| `<rd-card>` | `title?`, `accent?` (`info\|success\|warn\|danger\|muted`) | Bordered/elevated block. |

### Information blocks

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-callout>` | **`type`** (`info\|success\|warn\|danger\|note`), `title?` | Aside with icon and colored border. |
| `<rd-kv>` | — | Metadata block. Children must be `<rd-row>`. |
| `<rd-row>` | **`key`** | Inside `<rd-kv>` only. Value is the element's content. |
| `<rd-badge>` | `variant?` (`info\|success\|warn\|danger\|muted`) | Inline status pill. |
| `<rd-stat>` | **`value`**, `label?`, `trend?` (`up\|down\|flat`), `delta?`, `tone?` (`positive\|negative\|neutral`) | Big-number dashboard tile. Pair with `<rd-cols>` for status pages. |
| `<rd-quote>` | `author?`, `cite?`, `source-url?` | Attributed block quote. If `source-url` is set, the citation links to it. |

### Comparison and code

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-compare>` | **`headers`** (comma-separated) | Decision matrix. Children must be `<rd-row-cells>`. |
| `<rd-row-cells>` | **`label`** | One row in `<rd-compare>`. Children must be `<rd-cell>`. |
| `<rd-cell>` | `tone?` (`positive\|negative\|neutral`) | One cell. Tone tints background. |
| `<rd-code>` | `lang?`, `title?` | Code block with header bar + copy button. Indent stripped. |
| `<rd-figure>` | `caption?` | Wraps `<img>`, `<svg>`, or `<rd-mermaid>` with a centered caption. |

### Sequenced and interactive

| Tag | Attributes | Notes |
| --- | --- | --- |
| `<rd-tabs>` | — | Tabbed content. Children must be `<rd-tab>`. |
| `<rd-tab>` | **`label`**, `active?` | One pane. First tab is active unless one has `active`. |
| `<rd-timeline>` | — | Vertical timeline. Children must be `<rd-event>`. |
| `<rd-event>` | **`date`**, `title?` | One event marker. |
| `<rd-detail>` | **`summary`**, `open?` | Collapsible section. Native `<details>`; works without JS. |
| `<rd-checklist>` | — | Action-item list. Children must be `<rd-task>`. |
| `<rd-task>` | `done?`, `assignee?`, `due?` | One item with checkbox and optional metadata. |
| `<rd-mermaid>` | — | Lazy-loads mermaid from CDN; renders the diagram from text content. |
| `<rd-toc>` | `levels?` (default `"2,3"`), `title?` (default `"On this page"`) | Auto-generated TOC from `<h2>`/`<h3>` inside the parent `<rd-page>`. |

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

`examples/showcase.html` exercises every component. `examples/status-onepager.html` shows a realistic dashboard built from `<rd-stat>`, `<rd-checklist>`, `<rd-callout>`, `<rd-detail>`, and `<rd-timeline>`.

## Templates

- **`plan`** — title, problem callout, goals, steps timeline, risks, open questions, acceptance criteria.
- **`research`** — summary callout, TOC, findings, comparison matrix, recommendation, references.
- **`comparison`** — context, criteria, comparison matrix, trade-offs grid, recommendation.

Scaffold with `richdoc new <output> --template <name>`.

## Extending the framework

See `AUTHORING.md`. The short version: each component is one folder under `src/components/<name>/` with three files (`*.ts`, `*.css`, `*.schema.ts`). Add the import to `src/registry.ts`, `src/schema-registry.ts`, and `src/styles/index.css`, then run `bun run build` from the `richdoc/` root. The CLI picks up the new tag automatically because it reads the regenerated `assets/schema.json`.

## Limitations

- **One document per file.** No multi-page nav or shared assets across files (deferred to a later milestone).
- **Tabs, mermaid, TOC, copy button need JavaScript.** All other components work with CSS alone.
- **Mermaid requires internet** on first render (CDN load). Falls back to showing the raw diagram source if offline.
- **No Shadow DOM.** Embedding a richdoc fragment inside an unrelated page may leak styles. The framework assumes the richdoc occupies the whole page.
- **Browser-only consumer.** Use markdown if the doc must render on GitHub, in plaintext email, or in a CLI pager.
- **Theming.** The default theme is `editorial-warm` (warm paper, terracotta accent, Fraunces + Inter). Mode follows the system unless overridden. Override at the document level with `<rd-page theme="editorial-warm" mode="dark">`, or globally with `<html data-theme="…" data-mode="…">`. To add another theme, see `AUTHORING.md` → *Adding a theme*.
- **Fonts.** Fraunces (display) and Inter (body) are loaded from Google Fonts at render time. Offline docs fall back to a system serif + sans stack — still readable, but not the editorial look. Self-hosting is intentionally not the default; the framework's promise of "one HTML file plus two assets" stays intact.
