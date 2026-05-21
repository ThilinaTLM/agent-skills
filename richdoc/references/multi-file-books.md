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

## Implicit behaviors

Do **not** write attributes for any of these:

- **Active chapter** is detected by matching `location.pathname` against each `<rd-chapter href>`. Trailing-slash paths are normalised to `index.html`.
- **In-page headings** for the active chapter are merged inline under that chapter in the sidebar (Sphinx-style). One element produces both kinds of navigation.
- **Prev / next bands** are auto-injected at the top of `<rd-page>` (after `<rd-banner>` if present) and the bottom. Order comes from the chapter tree in document order; group headers (`<rd-chapter>` with no `href`) are skipped.
- **Group headers** are non-clickable section labels. Use them to organise chapters into chapter groups.
- **Title** is the chapter's text content, not a `title=` attribute. Whitespace is collapsed.

## Authoring rules

1. **Copy the `<rd-toc>` block verbatim into every page** in the book. There is intentionally no build step and no cross-file fetch — the chapter list must be present in each file. Re-order chapters by editing every page (typically only a handful). The list is stable and only changes when the book's structure changes.
2. **Do not hand-write prev/next.** `<rd-toc>` injects them. Hand-written copies will collide.
3. **Use relative `href` paths** (`./foo.html`, `../bar.html`). `richdoc lint` checks that each relative href resolves to a file on disk. Absolute URLs are allowed (external appendix) but the active-chapter / prev-next math treats them as ordinary entries.
4. **`<rd-toc title="…">` is the book title.** It shows as the rail's eyebrow and the narrow-mode bar label. The chapter title is the bar's current-item label.

See `examples/book/` for a multi-file walkthrough with subdirectories.

## Limitations

- Multi-file books **duplicate the chapter list**. Each chapter file contains the same `<rd-toc>` block. This is intentional — the format must work without a CLI build step and without runtime cross-file fetch (modern browsers block `fetch()` from `file://`).
- The same lock-in applies to renaming chapters: change in every file or lint will flag the broken hrefs.
