# confluence — downloading pages

`confluence download` pulls one Confluence page, a subtree, or a whole
space into a local directory. The output is designed for two
consumers:

- **AI agents**, which read `pages.jsonl` directly. Every row carries
  the full v2 API payload plus the page's **storage-format XML body**
  — the same representation Confluence accepts back on
  `page update`. That makes round-tripping (edit → re-upload) lossless.
- **Humans**, who can optionally get a `.md` sidecar per page. The
  markdown is best-effort and read-only.

The skill was push-only before this command existed. With `download`
the supported edit loop is now: **pull → edit storage XML → push**.

## Quick recipes

```bash
# One page from a URL the user pasted.
confluence download \
    "https://acme.atlassian.net/wiki/spaces/DEV/pages/123456/Title" \
    -o ./pulled

# Page + all descendants up to 3 levels, with attachments and markdown.
confluence download 123456 \
    -o ./pulled --recurse --depth 3 --markdown --attachments

# Look up by title within a space.
confluence download --space-key DEV --title "How to deploy" -o ./pulled

# Whole space (capped by --limit).
confluence download --space-key DEV -o ./pulled --limit 500
```

## Inputs

`PAGE_ID_OR_URL` accepts:

- a numeric Confluence page id (`123456`);
- a viewer URL: `https://<site>/wiki/spaces/<KEY>/pages/<ID>[/<Title>]`;
- a `?pageId=<ID>` query-string URL (older share links);
- a relative `/wiki/spaces/...` path.

**TinyLinks** (`https://<site>/wiki/x/...`) are rejected — they need
an HTTP redirect to resolve. Open the link in a browser and use the
expanded URL.

## Output layout

```
OUT_DIR/
  manifest.json                       # always
  pages.jsonl                         # always — one row per page
  pages/
    <safe-title>--<id>.md             # only with --markdown
  attachments/
    <pageId>/<filename>               # only with --attachments
```

`<safe-title>` is the title slugged to ASCII (lowercase, runs of
non-alphanumeric collapsed to `-`, max 80 chars). The page id suffix
guarantees uniqueness.

Attachments are nested by `pageId` so two pages can have attachments
with the same filename without colliding.

## `pages.jsonl` row schema

One JSON object per line. Stable schema, additive-only:

```json
{
  "schema": "confluence.page.dump.v1",
  "id": "123456",
  "title": "How to deploy",
  "spaceId": "789",
  "spaceKey": "DEV",
  "parentId": "654321",
  "version": 7,
  "createdAt": "2024-11-02T08:13:11Z",
  "updatedAt": "2025-01-14T15:42:00Z",
  "authorId": "abc-uuid",
  "webui": "/spaces/DEV/pages/123456/How+to+deploy",
  "url": "https://acme.atlassian.net/wiki/spaces/DEV/pages/123456/How+to+deploy",
  "body": {
    "representation": "storage",
    "value": "<p>…XHTML with ac:* / ri:* macros…</p>"
  },
  "attachments": [
    {
      "id": "att987",
      "title": "diagram.png",
      "mediaType": "image/png",
      "fileId": "abc-def",
      "fileSize": 24576,
      "downloaded": true,
      "path": "attachments/123456/diagram.png"
    }
  ],
  "markdown": "pages/how-to-deploy--123456.md"
}
```

Notes:

- Pages appear in depth-first traversal order so you can reconstruct
  the hierarchy by streaming.
- `attachments[].path` and `attachments[].downloaded` are populated
  only when `--attachments` was used; otherwise the entries record
  metadata only and `downloaded` is `false`, `path` is `null`. If a
  specific attachment fetch fails, the record gains an `error` field
  with the message and `downloaded` stays `false`.
- `markdown` is `null` unless `--markdown` was used.
- `createdAt`, `updatedAt`, and `authorId` come from the v2 page
  payload and may be `null` for older content.

## `manifest.json` schema

Sidecar so agents (or humans) can orient before scanning rows:

```json
{
  "schema": "confluence.dump.v1",
  "site": "https://acme.atlassian.net",
  "space": {"id": "789", "key": "DEV", "name": "Developer Hub"},
  "rootPageId": "123456",
  "exportedAt": "2026-05-28T10:11:12Z",
  "exportedBy": "confluence-cli/0.1.0",
  "pageCount": 12,
  "attachmentCount": 4,
  "truncated": false,
  "options": {
    "recurse": true,
    "depth": null,
    "limit": 200,
    "markdown": true,
    "attachments": true
  },
  "tree": [
    {
      "id": "123456", "title": "How to deploy", "parentId": null,
      "url": "https://…", "jsonlLine": 1,
      "markdown": "pages/how-to-deploy--123456.md"
    }
  ],
  "markdownNote": "Best-effort conversion. Do NOT re-upload from markdown — edit pages.jsonl 'body.value' (storage XML) and use 'confluence page update --body-file'."
}
```

`truncated: true` means the walk hit `--limit` and there were almost
certainly more pages. Re-run with a higher `--limit` to be sure.

## Success envelope (stdout)

```json
{
  "ok": true,
  "site": "https://acme.atlassian.net",
  "profile": "work",
  "outputDir": "/abs/path/OUT_DIR",
  "manifest": "/abs/path/OUT_DIR/manifest.json",
  "jsonl": "/abs/path/OUT_DIR/pages.jsonl",
  "pageCount": 12,
  "attachmentsDownloaded": 4,
  "markdownGenerated": 12,
  "truncated": false,
  "pages": [
    {"id": "123456", "title": "How to deploy",
     "url": "https://acme.atlassian.net/wiki/spaces/DEV/pages/123456/…"}
  ],
  "nextStep": {
    "summary": "Edit the storage body in pages.jsonl …",
    "argv": ["confluence", "page", "update", "123456",
             "--body-file", "<edited.storage.xml>"]
  }
}
```

The `nextStep.argv` always references the **first** page in the dump
so an agent has a known-good follow-up command.

## Edit-and-reupload recipe

```bash
# 1. Pull.
confluence download "https://acme.atlassian.net/wiki/spaces/DEV/pages/123456/T" \
    -o ./pulled

# 2. Extract the body for editing. Using jq:
jq -r 'select(.id == "123456") | .body.value' ./pulled/pages.jsonl \
    > 123456.storage.xml

# 3. Edit 123456.storage.xml. LLMs are good at storage XML — it's
#    just XHTML with ac:*/ri:* namespaced macros. Preserve the macro
#    structure when you can; the publisher does not validate
#    aggressively but Confluence will reject syntactically broken XML.

# 4. Push back.
confluence page update 123456 \
    --body-file 123456.storage.xml \
    --comment "Updated by agent"
```

## Markdown conversion — what's handled

The markdown converter (only enabled with `--markdown`) is pure
Python (requires the `[markdown]` extra: `pip install markdownify`).

Handled storage elements:

| Storage construct | Markdown output |
|---|---|
| Plain HTML (`p`, headings, lists, tables, `strong`, `em`, `code`, links, images) | Standard markdown. |
| `ac:structured-macro` `info` / `note` / `warning` / `tip` / `panel` | `> **Label**\n> ...` blockquote with a `callout-X` class hint. |
| `ac:structured-macro` `code` | Fenced code block with language. |
| `ac:structured-macro` `expand` | `<details><summary>…</summary>…</details>` (HTML; renders in most markdown viewers). |
| `ac:structured-macro` `status` | `[Label]` plain text. |
| `ac:structured-macro` `toc` | Placeholder line. |
| `ac:link` → `ri:page` | Hyperlink resolved against the dumped page tree; falls back to plain text if the target isn't in the dump. |
| `ac:link` → `ri:attachment` | Link to the local attachment file (with `--attachments`) or the Confluence public URL. |
| `ac:image` → `ri:attachment` | `![alt](attachments/<pid>/<file>)` or `![alt](https://site/wiki/download/…)` when attachments aren't downloaded. |
| `ac:emoticon` | Equivalent Unicode (✅, ❌, ⚠️ …). |
| `ac:task-list` / `ac:task` | GitHub-style `- [ ]` / `- [x]` list. |
| Any other `ac:*` macro | `<!-- unsupported confluence macro: NAME -->` placeholder with the rich-text body content preserved underneath. |

**Always lossy.** Layouts, columns, drawio diagrams, mermaid macros,
user mentions, page properties, status reports, etc. all degrade.
**Do not** convert markdown back to storage XML and re-upload —
there is no markdown→storage path in this skill, and any external
tool you use will lose the macros that the round trip needs.

## Performance and limits

- The walk is bounded by `--limit` (default `200`) as a runaway
  safety. Each page is one v2 API call plus one attachments-list
  call plus N attachment-download calls if `--attachments` is on.
- `--depth N` (when recursing) caps the nesting below the starting
  page (1 = direct children only).
- Pages stream straight to disk one at a time, so memory usage stays
  bounded even for big spaces.
- No automatic backoff on 429. If you hit rate limits, re-run with a
  smaller `--limit` or a tighter `--depth`.

## Error codes specific to download

| Code | Cause |
|---|---|
| `INVALID_PARAMS` | Bad/empty page reference; `--limit`/`--depth` invalid; conflicting flags; no page reference and no `--space-key`. |
| `NOT_FOUND` | Page id or `--title` does not resolve in the space. |
| `FILE_EXISTS` | Output directory is non-empty without `--force`. |
| `MISSING_DEPENDENCY` | `--markdown` requested but `markdownify` is not installed. Install with `uv pip install -e .[markdown]`. |
| `UNSUPPORTED` | `page get --format adf` (ADF body format is not implemented yet). |
| Standard auth / upstream codes (see `references/auth.md`). | |

## See also

- [auth.md](auth.md) — credential resolution.
- [richdoc-bundles.md](richdoc-bundles.md) — the publish side.
- `../SKILL.md` — top-level overview.
