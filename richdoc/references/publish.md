# `richdoc publish` — push richdoc HTML to remote systems

Currently the only supported target is Confluence Cloud, via the REST API. The
publisher creates or updates pages in **an existing space** (the abandoned
`html-confluence` zip exporter could only create new spaces — useless for any
ongoing workflow).

## Quick start

```bash
# 1. Configure once per shell. None of these are persisted to disk.
export CONFLUENCE_SITE="https://acme.atlassian.net"
export CONFLUENCE_EMAIL="me@acme.com"
export CONFLUENCE_TOKEN="<your atlassian api token>"
export CONFLUENCE_SPACE_KEY="DEV"

# 2. Browse available spaces and pick the one you want in $CONFLUENCE_SPACE_KEY.
#    (This subcommand ignores $CONFLUENCE_SPACE_KEY — it's how you discover it.)
richdoc publish confluence spaces
# → {"ok":true,"spaces":[{"id":"…","key":"DEV","name":"Engineering",…}]}

# 3. Browse pages in $CONFLUENCE_SPACE_KEY to pick a parent.
richdoc publish confluence pages -q "Docs root"

# 4. Push the doc.
richdoc publish confluence push docs/data-design.html --parent-id 1234567
```

Re-running the same `push` updates the existing pages in place (matched by
`(space, parent, title)`), re-uploads any changed attachments under the
same filenames, and bumps each page's version. Idempotent by design.

## Configuration

All configuration comes from environment variables. There are no flags
for these values and no interactive prompts.

| Variable | Required by | Value |
|---|---|---|
| `CONFLUENCE_SITE` | all subcommands | e.g. `https://acme.atlassian.net` (bare host is auto-prefixed with `https://`) |
| `CONFLUENCE_EMAIL` | all subcommands | Atlassian account email |
| `CONFLUENCE_TOKEN` | all subcommands | API token — generate at <https://id.atlassian.com/manage-profile/security/api-tokens> |
| `CONFLUENCE_SPACE_KEY` | `pages`, `push` | Target space key, e.g. `DEV` (use `spaces` to discover) |

- Auth is HTTP Basic with `email:api_token` per Atlassian's documented model.
- Tokens **never appear** in logs, JSON envelopes, or temp files.
- A missing or empty required variable exits with `code: CONFIG_MISSING`
  and a `missing[]` list naming the unset vars — the CLI never blocks on
  a prompt and never reads stdin for credentials.
- A present-but-malformed value (e.g. a `CONFLUENCE_SITE` that isn't a
  URL) exits with `code: AUTH_ERROR`.
- A read-only `/spaces?limit=1` probe runs before any write call so bad
  credentials fail fast.

## Subcommands

### `spaces`

```bash
richdoc publish confluence spaces [-q TEXT] [--limit N]
```

List spaces visible to the token. `-q` filters by key / name substring
(case-insensitive). Returns:

```json
{"ok": true,
 "site": "https://acme.atlassian.net",
 "spaces": [{"id":"…","key":"DEV","name":"Engineering","type":"global",
             "homepageId":"…","url":"https://…/wiki/spaces/DEV"}]}
```

### `pages`

```bash
richdoc publish confluence pages [-q TEXT] [--parent-id ID] [--limit N]
```

List pages in `$CONFLUENCE_SPACE_KEY`. `-q` filters by title substring.
`--parent-id` restricts to direct children of a specific page. Returns
each page with `{id, title, parentId, spaceId, version, url}`.

### `page-by-id`

```bash
richdoc publish confluence page-by-id PAGE_ID
```

Resolve a single page id to `{id, title, parentId, spaceId, version, url}`.
Useful for confirming an `--parent-id` value before pushing.

### `push`

```bash
richdoc publish confluence push INPUT [OPTIONS]
```

Publish a richdoc HTML file (single document or whole book) into
`$CONFLUENCE_SPACE_KEY`.

```
--parent-id ID                Parent page id; new pages land under it.
--parent-title TEXT           Resolve a parent by exact title (must be unique).
--page-id ID                  Force update of this specific page id.
--title TEXT                  Title for the single-file case (book mode
                              titles come from the rd-toc chapter labels).
--title-prefix TEXT           Prepended to every page title (e.g. "[richdoc] ").
--no-book                     Single-file mode — ignore rd-toc.
--dry-run                     Walk every chapter, return the storage XML +
                              attachment plan inside the JSON envelope,
                              don't touch any write endpoint.
--no-render-diagrams          Skip Kroki rendering of rd-diagram; embed
                              source in a code macro instead.
--no-render-math              Skip Kroki rendering of rd-math; emit italic
                              source instead.
--diagram-endpoint URL        Kroki-compatible server for math + diagrams.
                              Default: https://kroki.io.
--include-remote-images       Fetch http(s) <img> sources and upload them
                              as attachments. Default: link as-is.
--comment TEXT                Version comment on each updated page.
                              Default: "Updated via richdoc CLI".
```

The success envelope is:

```json
{"ok": true,
 "input": "/path/to/doc.html",
 "site": "https://acme.atlassian.net",
 "space": {"id": "…", "key": "DEV"},
 "parentId": "1234567",
 "book": true,
 "pages": [
   {"id":"…","title":"Overview","parent_id":"1234567",
    "url":"https://…","action":"created","version":2},
   {"id":"…","title":"Chapter 1","parent_id":"<above id>",
    "url":"https://…","action":"updated","version":5}
 ],
 "attachments_uploaded": 4,
 "attachments_skipped": 3,
 "diagrams_rendered": 2,
 "diagrams_failed": 0,
 "math_rendered": 1,
 "math_failed": 0,
 "dropped": ["rd-chart[sparkline]", "rd-icon", "rd-toc"],
 "missing": []}
```

`action` is one of `created`, `updated`, `planned` (dry-run only).

## Book hierarchy

For a book (entry file linked via `<rd-toc>`):

- The **entry chapter** is published under `--parent-id` (or the space root).
- Every other chapter nests under either:
  - The page-backed TOC parent (if there is one in the `<rd-toc>` tree), or
  - The entry chapter (fallback — including for chapters under a group
    header that has no `href`).
- Group headers (`<rd-chapter>` without `href`) don't create a Confluence
  page; their children inherit the group's effective parent.
- Confluence's native sidebar shows the resulting tree.

## rd-* component mapping

| Component | Confluence rendering |
|---|---|
| `rd-page` | unwrapped |
| `rd-hero` | `<h1>` + meta paragraph (eyebrow · lede · meta) |
| `rd-section` | `<h2>` + body |
| `rd-card` | `<h3>` + body |
| `rd-cols` | linearised |
| `rd-callout`, `rd-banner` | native `info` / `note` / `tip` / `warning` macros |
| `rd-detail` | native **`expand`** macro — collapsibility preserved |
| `rd-code` / `rd-diff` / `rd-shell` / `<pre>` | native **`code`** macro with language + title |
| `rd-checklist` | native `<ac:task-list>` with interactive checkboxes |
| `rd-math` (block + inline) | Kroki TikZ → PNG attachment → `<ac:image>` |
| `rd-diagram` | Kroki → PNG attachment → `<ac:image>` |
| `rd-figure` | inner image + `<p><em>caption</em></p>` |
| `rd-kv` (inline) | `<ul>` with `<strong>key:</strong> value` items |
| `rd-kv` (stacked) | `<ul>` with one entry per row, key in `<strong>` + `<br/>` body |
| `rd-compare`, `rd-rubric`, `rd-api`, `rd-chart` (non-sparkline) | native `<table>` |
| `rd-stat`, `rd-progress`, `rd-update` | `<p>` with bold value + meta |
| `rd-tabs` | each tab as `<h3>` + body |
| `rd-timeline`, `rd-pros-cons` | `<ul>` |
| `rd-steps` | `<ol>` |
| `rd-decision` | `<h2>` + status meta + body |
| `rd-references` + scattered `rd-ref` | auto-generated `<ol>` bibliography after the body, cited-first ordering |
| `rd-cite` | `<sup>[n]</sup>` numbered by cite order |
| `rd-badge` | `<strong>[label]</strong>` |
| `rd-icon` | label text only (no glyph) |
| `rd-toc` | dropped — Confluence's native sidebar shows the page tree |
| `rd-chart variant="sparkline"` | dropped |
| `<img src="local.png">` | uploaded as attachment + `<ac:image>` reference |
| `<a href="./chapter.html">` | href rewritten to the resolved Confluence URL |

## Attachments

- Math + diagram PNGs use stable filenames derived from the SHA-1 of the
  rendered bytes: `math-<sha1[:12]>.png` / `diag-<sha1[:12]>.png`. Two
  identical renders share one upload.
- User `<img>` files use the hash of the file contents — same trick.
- Uploads go through the v1 `PUT /wiki/rest/api/content/{pageId}/child/attachment`
  endpoint, which is **create-or-update by filename**. Confluence handles
  versioning automatically.
- Re-publishing an unchanged doc skips every attachment upload (matched by
  filename); the `attachments_skipped` counter reflects this.
- Stale attachments from a prior publish are **not** auto-deleted — the
  user prunes manually if needed.

## Dry-run

```bash
richdoc publish confluence push doc.html --dry-run
```

Walks every chapter, runs the storage-XML converter, and reports what
*would* happen — no `POST /pages`, no `PUT /pages`, no attachment
upload. The envelope includes a `bodies` array with the full storage XML
preview and the attachment plan for each chapter, plus
`"action": "planned"` on every page entry.

Useful for previewing macro layout before pushing into a sensitive space.

## Error codes

| Code | Cause |
|---|---|
| `CONFIG_MISSING` | One or more required `CONFLUENCE_*` env vars are not set. The envelope lists them under `missing[]`. |
| `AUTH_ERROR` | Bad credentials, or a present env var value is malformed (e.g. site URL). |
| `PERMISSION_DENIED` | Token is valid but lacks write access to the space. |
| `NOT_FOUND` | Space key, parent id, or `--parent-title` doesn't exist. |
| `VERSION_CONFLICT` | Someone else updated the page during the publish; retried once, then surfaced. |
| `ATTACHMENT_TOO_LARGE` | Confluence's per-attachment size limit (~100 MB default). Disable diagrams or reduce image size. |
| `AMBIGUOUS_MATCH` | `--parent-title` matched more than one page; use `--parent-id` instead. |
| `UPSTREAM_ERROR` | Server-side / network error from Confluence or Kroki. |

## Limits & non-goals

- **Confluence Cloud only.** The v2 REST API doesn't exist on Data Center.
- **Pages only.** Whiteboards, databases, and blog posts aren't published.
- **No content sync back from Confluence.** Push only.
- **No auto-deletion** of pages whose source chapter was removed.
- **No native diagram macros** even on tenants with the Mermaid app
  installed — we render to PNG for portability across editions.
- **No OAuth flow** — API tokens are the documented frictionless model
  for personal / agent use.
