# richdoc — multi-file books

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

  <rd-hero title="Setup"></rd-hero>
  …content…
</rd-page>
```

## How book discovery works

The `<rd-toc>` block already in each chapter file is the source of truth for the book — there is no separate manifest. The same tree is used by three consumers:

- **The browser runtime (`richdoc.js`).** Each chapter's `<rd-toc>` is parsed once, the active chapter is matched against `location.pathname`, and prev/next bands are injected at the top and bottom of `<rd-page>`. The sidebar uses the same tree.
- **The linter (`richdoc lint`).** Reads the file's `<rd-toc>`, walks each `<rd-chapter href>` to find linked chapters on disk, and compares each peer's `<rd-toc>` against this file's. Any chapter that doesn't match (added/removed/reordered/retitled) is reported as `book-toc-drift`. Hrefs are compared by resolved target, so `./other.html` at the book root and `../other.html` from a subdirectory are equivalent as long as they resolve to the same file.
- **The publisher (`richdoc confluence publish`).** Treats the entry chapter's `<rd-toc>` as the canonical tree, walks it to discover every chapter, and publishes them in TOC order. Each chapter nests under the page that backs its parent `<rd-chapter>` (or under the user-supplied `--parent-id` for the entry). Group headers (`<rd-chapter>` without `href`) become non-clickable section labels in the inline Contents block and pass their children up to the entry's parent.

A document is "in book mode" when at least one `<rd-chapter>` inside its `<rd-toc>` carries an `href` that resolves to a sibling file. Single-file docs (in-page TOCs with no hrefs) keep working as before.

## Implicit behaviors

Do **not** write attributes for any of these:

- **Active chapter** is detected by matching `location.pathname` against each `<rd-chapter href>`. Trailing-slash paths are normalised to `index.html`.
- **In-page headings** for the active chapter are merged inline under that chapter in the sidebar (Sphinx-style). One element produces both kinds of navigation.
- **Prev / next bands** are auto-injected at the top of `<rd-page>` (after `<rd-banner>` if present) and the bottom. Order comes from the chapter tree in document order; group headers (`<rd-chapter>` with no `href`) are skipped.
- **Group headers** are non-clickable section labels. Use them to organise chapters into chapter groups.
- **Title** is the chapter's text content, not a `title=` attribute. Whitespace is collapsed.

## Authoring rules

1. **Copy the `<rd-toc>` block into every page** in the book. There is intentionally no build step and no cross-file fetch — the chapter list must be present in each file. Re-order chapters by editing every page (typically only a handful). `richdoc lint` enforces consistency: rule `book-toc-drift` errors if any chapter's `<rd-toc>` doesn't match the others. There is no autofix for this rule; reconcile the canonical block manually (typically by copying the entry file's `<rd-toc>` into every chapter).
2. **Do not hand-write prev/next inside `<rd-hero>`.** `<rd-toc>` injects the bands automatically. Rule `hero-nav-redundant` flags any `<a>` children whose href resolves to another book chapter (or whose text matches `prev|next|up|home|index|↑|←|→`), and any `Prev:/Next:/Up:` segments in the hero's `meta` attribute. Both the HTML view and the Confluence publisher also drop these silently in book mode as a safety net, but lint is the first line of defence. Run `richdoc lint --fix <file-or-dir>` to strip them.
3. **Use relative `href` paths** (`./foo.html`, `../bar.html`). `richdoc lint` checks that each relative href resolves to a file on disk. Subdirectories are fine — the drift check compares resolved targets, not literal strings, so a book entry can link `./ops/runbook.html` while `ops/runbook.html` itself links `../ops/escalation.html` for a sibling. Absolute URLs are allowed (external appendix) but the active-chapter / prev-next math treats them as ordinary entries.
4. **`<rd-toc title="…">` is the book title.** It shows as the rail's eyebrow and the narrow-mode bar label. The chapter title is the bar's current-item label.

## Publishing a book

```bash
richdoc confluence publish docs/             # entry resolves to docs/index.html
richdoc confluence publish docs/index.html   # equivalent
```

`publish` accepts a directory or the entry file. For a directory, the entry chapter resolves to `<dir>/index.html`; if `index.html` is missing the command fails with `INVALID_PARAMS` instead of guessing. Before any network call, `publish` runs `richdoc lint` against the input; any error blocks the publish and is returned in the `lint.files[]` field of the error envelope. Pass `--no-lint` only when intentionally debugging a publish.

See [references/publish.md](publish.md) for the full publish contract (page hierarchy, attachments, error codes) and [references/migrating-to-book-mode.md](migrating-to-book-mode.md) for converting an existing flat doc set to a book.

See `examples/book/` for a multi-file walkthrough with subdirectories.

## Limitations

- Multi-file books **duplicate the chapter list**. Each chapter file contains a matching `<rd-toc>` block. This is intentional — the format must work without a CLI build step and without runtime cross-file fetch (modern browsers block `fetch()` from `file://`).
- Renaming or reordering a chapter means editing every file's `<rd-toc>`. Lint flags the drift; the agent reconciles.
