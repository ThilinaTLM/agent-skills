# Migrating a flat doc set to a richdoc book

This guide is for taking an existing directory of richdoc HTML files —
each one a standalone page that hand-links to its siblings — and
opting into **book mode**: shared `<rd-toc>` navigation, auto-injected
prev/next bands, cross-file link rewriting at publish time. Five
mechanical steps, no manifest, no build step.

## Starting point

Assume a directory like this, with no shared TOC:

```
docs/
  index.html
  01-overview.html
  02-architecture.html
  …
  10-sandbox-runtime.html
  richdoc.css
  richdoc.js
```

Each file has its own `<rd-hero>` and content; chapters link to one
another with bare `<a href="./other.html">` calls inside the hero or in
prose. Lint passes per-file.

## Step 1 — Pick an entry chapter

Convention: `index.html`. The publisher resolves a directory input to
`<dir>/index.html`; the runtime treats `index.html` as the active
chapter for a trailing-slash URL. If you don't have one, rename the
file that should be the book's landing page.

## Step 2 — Write the canonical `<rd-toc>` block

Choose the chapter list and order once. Put the `<rd-toc>` block at
the top of `<rd-page>` (after `<rd-banner>` if present):

```html
<rd-toc title="My Handbook">
  <rd-chapter href="./index.html">Home</rd-chapter>
  <rd-chapter href="./01-overview.html">Overview</rd-chapter>
  <rd-chapter href="./02-architecture.html">Architecture</rd-chapter>
  …
  <rd-chapter>Operations
    <rd-chapter href="./09-security.html">Security</rd-chapter>
    <rd-chapter href="./10-sandbox-runtime.html">Sandbox runtime</rd-chapter>
  </rd-chapter>
</rd-toc>
```

Notes:

- `<rd-toc title="…">` is the book title.
- Chapter title is the element's text content, not a `title=` attribute.
- A `<rd-chapter>` without `href` is a group header (non-clickable).
- Relative `href` only. Lint will check each resolves on disk.

## Step 3 — Copy the `<rd-toc>` block into every chapter

The same block (or one that resolves to the same chapters) must live in
every chapter file. From a subdirectory, hrefs change to walk back up
(`../index.html` instead of `./index.html`) — lint compares resolved
targets, not raw strings, so this works.

Verify with:

```bash
richdoc lint docs/
```

Any `book-toc-drift` error means a chapter's TOC doesn't match the
others. There is no autofix for drift — copy the canonical block (or
adjust the offending file's hrefs) by hand.

## Step 4 — Strip legacy hero navigation

Pre-book chapters typically have hand-written prev/next links inside
`<rd-hero>`, plus `Prev:/Next:/Up:` text in the `meta` attribute:

```html
<!-- before -->
<rd-hero
  eyebrow="05 · Authoring guide"
  title="Plugin SDK"
  lede="…"
  meta="Up: index · Prev: 04 Plugin System · Next: 06 Pods & Coordination">
  <a href="./index.html">← Index</a>
  <a href="./04-plugin-system.html">Prev</a>
  <a href="./06-pod-and-coordination.html">Next →</a>
</rd-hero>
```

In book mode `<rd-toc>` auto-injects prev/next bands at the top and
bottom of every chapter. The hand-written nav double-renders and
should go. Strip it everywhere with one command:

```bash
richdoc lint docs/ --fix
```

The `hero-nav-redundant` rule fires when book mode is active *and*
`<rd-hero>` has `<a>` children whose href resolves to another book
chapter (or whose text matches `prev|next|up|home|index|↑|←|→`), or
when `meta` contains `Prev:/Next:/Up:` segments. `--fix` removes the
matched children and segments. The fix is idempotent; re-running it
makes no changes.

```html
<!-- after --fix -->
<rd-hero eyebrow="05 · Authoring guide" title="Plugin SDK" lede="…">
</rd-hero>
```

## Step 5 — Confirm and publish

```bash
richdoc lint docs/                           # expect zero errors
richdoc confluence publish docs/ \
    --parent-id 65934 \
    --title-prefix "[Handbook] "
```

`publish` accepts the directory directly. It runs `richdoc lint` before
any network call and refuses to publish on lint errors, so the explicit
lint step in the line above is redundant once you trust the workflow.

## Failure modes to expect

- **`book-toc-drift` after step 3** — a chapter's `<rd-toc>` differs
  from this file's. Most often a forgotten copy when the canonical
  block was edited. Reconcile by hand; no autofix.
- **`hero-nav-redundant` after step 4** — `--fix` was skipped or the
  hero contains nav anchors lint didn't recognise. The renderer guard
  still drops the children at publish time (you'll see `rd-hero/a` in
  the envelope's `dropped[]`), but lint errors will block the publish
  until the source is cleaned.
- **`rd-chapter-href-missing`** — a chapter listed in `<rd-toc>`
  doesn't exist on disk. Typo in the href, or a deleted chapter
  someone forgot to remove from the TOC.

## What this gives you

Once a book is set up:

- Reordering or renaming a chapter is a one-edit-per-file change to the
  shared `<rd-toc>` block (or, with discipline, an edit to the entry's
  block followed by a paste into every other chapter — lint will tell
  you when you've missed one).
- `richdoc confluence publish docs/` is the only command needed
  for the full book; chapter pages nest correctly under the entry,
  cross-file links rewrite to Confluence URLs, prev/next bands are
  injected at the top and bottom of every page.
- Local browser viewing still works without a server — open
  `docs/index.html` and the sidebar + bands render from the same
  `<rd-toc>` source.
