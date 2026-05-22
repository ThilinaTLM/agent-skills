# confluence — publishing richdoc bundles

The `confluence` skill publishes
`richdoc.confluence.bundle.v1` directories produced by
`richdoc export confluence`. The two skills are deliberately
decoupled: this skill never imports any `richdoc_cli` code, and the
bundle format is the only contract between them.

## Bundle schema

```
<bundle_dir>/
  manifest.json
  pages/
    <safe-name>.storage.xml        # XHTML + ac:* macros
  attachments/
    <stable-filename>
```

`manifest.json`:

```json
{
  "schema": "richdoc.confluence.bundle.v1",
  "createdBy": "richdoc-cli 0.x",
  "input": "/abs/docs/index.html",
  "book": true,
  "pages": [
    {
      "key": "index.html",
      "source": "index.html",
      "title": "Overview",
      "parentKey": null,
      "storage": "pages/index.storage.xml",
      "attachments": [
        {"token": "@@ATTACHMENT:diag:abc123def@@",
         "filename": "diag-abc123def.png",
         "path": "attachments/diag-abc123def.png",
         "mime": "image/png",
         "align": "center",
         "inline": false}
      ],
      "links": [
        {"token": "@@RICHDOC_PAGE_URL:chapter-1.html@@",
         "targetKey": "chapter-1.html"}
      ],
      "dropped": [],
      "missing": []
    }
  ],
  "summary": {
    "attachments": 1,
    "diagramsRendered": 1,
    "diagramsFailed": 0,
    "mathRendered": 0,
    "mathFailed": 0
  }
}
```

Field rules:

- `schema` must be the literal string `richdoc.confluence.bundle.v1`.
  Anything else is rejected with `INVALID_BUNDLE`.
- `pages` is ordered; the first entry is the bundle root.
- `parentKey` either references another page's `key` or is `null`.
- `storage` and every `attachments[].path` must resolve **inside** the
  bundle directory. Path-traversal is rejected.
- `links[].targetKey` must reference a `key` that exists in `pages`;
  unresolved links fail the publish with `INVALID_BUNDLE` *before* any
  network call.

## Publish algorithm

`confluence publish-bundle <bundle>` is a deterministic two-pass
process:

1. **Validate.** Read the manifest, reject path traversal and unknown
   schema, fail-fast on broken cross-page link tokens.
2. **Resolve target.** Look up the space by key (`--space-key` or the
   profile default). If `--parent-title` was passed, resolve it to a
   unique page id; otherwise use `--parent-id` (or the profile's
   `parentId`).
3. **First pass — page resolution.** For each page in manifest order:
    - compute the Confluence parent: the previously resolved page for
      the manifest's `parentKey`, falling back to `--parent-id` for
      root pages;
    - apply `--title-prefix`;
    - find an existing page by `(space, parent, title)` (or `--page-id`
      for the first page);
    - create missing pages with a placeholder body so a real page id
      exists for cross-page link substitution.
4. **Second pass — body + attachments.** For each page:
    - upload attachments; skip ones Confluence already has under the
      same filename;
    - read the storage XML off disk;
    - substitute `@@ATTACHMENT:...@@` tokens with `<ac:image>`
      references built from the manifest's attachment entries;
    - substitute `@@RICHDOC_PAGE_URL:...@@` tokens with the resolved
      public URLs gathered in the first pass;
    - update the page body in one call. Retry once on
      `VERSION_CONFLICT`.

## Idempotency

Re-running `confluence publish-bundle` against the same bundle:

- Finds existing pages by `(space, parent, title)` and updates them in
  place — no duplicate pages.
- Confluence's `PUT .../attachment` endpoint is create-or-update by
  filename, and we skip uploads when an attachment with the target
  filename already exists. Math/diagram filenames are content-hashed
  by the producer (e.g. `diag-<sha1[:12]>.png`), so identical content
  always reuses the same upload.
- Stale attachments and pages from prior publishes are **not**
  auto-deleted; prune manually if a chapter is removed from the
  bundle.

## Dry run

```bash
confluence publish-bundle build/confluence-docs --dry-run
```

Reads the manifest, resolves the space and (if needed) the parent
title, then walks the page tree without calling `create` / `update` /
`attachment` endpoints. The envelope reports `action: "planned"` for
every page and includes the computed parent id for each, which is the
fastest way to verify the hierarchy before publishing.

## Success envelope

```json
{
  "ok": true,
  "bundle": "/abs/build/confluence-docs",
  "schema": "richdoc.confluence.bundle.v1",
  "site": "https://acme.atlassian.net",
  "profile": "work",
  "space": {"id": "...", "key": "DEV"},
  "parentId": "1234567",
  "book": true,
  "pages": [
    {"id": "...", "title": "Overview", "parent_id": "1234567",
     "url": "https://...", "action": "updated", "version": 5}
  ],
  "attachments_uploaded": 4,
  "attachments_skipped": 3,
  "unresolved_links": [],
  "dry_run": false
}
```

## Error codes

| Code | Cause |
|---|---|
| `INVALID_BUNDLE` | Missing manifest, wrong schema, path traversal, duplicate page key, broken cross-page link, etc. |
| `INVALID_PARAMS` | Conflicting flags (e.g. `--parent-id` and `--parent-title`). |
| `CONFIG_MISSING` | Credentials could not be resolved. See `references/auth.md`. |
| `AUTH_ERROR` | Confluence rejected the API token. |
| `PERMISSION_DENIED` | Token authenticated but lacks write access in the space. |
| `NOT_FOUND` | Space key, `--parent-id`, or `--parent-title` does not resolve. |
| `AMBIGUOUS_MATCH` | `--parent-title` matched more than one page; use `--parent-id`. |
| `VERSION_CONFLICT` | Someone updated a page during the publish; the publisher retries once and then surfaces this. |
| `ATTACHMENT_TOO_LARGE` | Confluence's per-attachment size limit (~100 MB by default). |
| `UPSTREAM_ERROR` | Network failure or 5xx from Confluence. |

## Limitations

- **Cloud only.** The v2 REST endpoints the client uses are
  Cloud-only; Data Center is not supported.
- **Push only.** No content sync back from Confluence.
- **No auto-deletion.** Removing a chapter from the bundle does not
  delete the matching Confluence page.
- **Single-namespace tokens.** Only `@@ATTACHMENT:...@@` and
  `@@RICHDOC_PAGE_URL:...@@` are recognised; other producer tokens
  pass through verbatim into the page body.
