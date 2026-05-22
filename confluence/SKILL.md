---
name: confluence
description: This skill should be used when the user asks to manage Confluence Cloud content from the command line — list/search Confluence spaces, list/create/update/delete Confluence pages, upload attachments, configure Confluence authentication, store API tokens securely, switch between Confluence profiles, or publish a richdoc-generated Confluence bundle. Triggers include "publish to Confluence", "update Confluence page", "list Confluence spaces", "Confluence auth", "Confluence login", "store Confluence token", "publish-bundle", or "send this to Confluence". For authoring polished HTML documents that will eventually be published to Confluence, use the `richdoc` skill first (`richdoc export confluence`) and then use this skill to publish the resulting bundle.
---

# confluence

CLI for managing Confluence Cloud content and publishing storage
bundles produced by other tools (notably `richdoc`). JSON output, no
interactive prompts.

## When to use confluence

- Browsing or searching Confluence spaces / pages.
- Creating, updating, or deleting Confluence pages from storage-format
  XML files.
- Uploading attachments to a page.
- Managing the auth profile(s) the agent uses to talk to Confluence.
- Publishing a `richdoc.confluence.bundle.v1` directory to a Confluence
  space (one-shot, idempotent, two-pass).

For authoring rich documents, use the `richdoc` skill. The two skills
share a documented on-disk bundle format and are deliberately
decoupled: `confluence` never imports richdoc code, and `richdoc` never
opens a Confluence connection.

## CLI Discovery

The CLI is located at `./confluence-cli/` relative to this SKILL.md.
Requires [`uv`](https://docs.astral.sh/uv/); the first call provisions
the Python environment.

| Platform         | Script                                              |
| ---------------- | --------------------------------------------------- |
| Unix/Linux/macOS | `confluence`                                        |
| Windows          | `confluence.cmd` (`confluence.ps1` also available)  |

| Command | Description |
| --- | --- |
| `confluence auth init --profile NAME [--site URL] [--email EMAIL] [--space-key KEY] [--token-env NAME]` | Write a profile entry to the user config file with a `<your-token-here>` placeholder. Returns `next_steps` for the human user. |
| `confluence auth profiles` | List profiles from project and user config. Token values never appear. |
| `confluence auth use PROFILE` | Set the user-config default profile. |
| `confluence auth logout --profile NAME [--keep-config]` | Forget a profile (removes the entry or just the token field). |
| `confluence auth status [--profile NAME] [--strict] [--no-verify]` | Resolve credentials, report `tokenSource` / `tokenLocation` / `secure`, and ping Confluence. |
| `confluence spaces [-q TEXT] [--limit N]` | List spaces visible to the token. |
| `confluence pages [--space-key KEY] [-q TEXT] [--parent-id ID] [--limit N]` | List pages in a space. |
| `confluence page-by-id PAGE_ID` | Resolve a page id to `{id, title, parentId, spaceId, version, url}`. |
| `confluence page get PAGE_ID [--body]` | Fetch one page's metadata. |
| `confluence page create --space-key KEY [--parent-id ID] --title TEXT --body-file FILE` | Create a page from a storage-format XML file. |
| `confluence page update PAGE_ID [--title TEXT] --body-file FILE [--comment TEXT]` | Update an existing page. |
| `confluence publish-bundle BUNDLE [...]` | Publish a `richdoc.confluence.bundle.v1` directory. |

## Authentication — the AI agent workflow

The CLI never accepts an API token as a flag, on stdin, or through any
other channel the AI agent can supply. The token MUST be entered by
the human user. The agent's job is to template the config file and
forward instructions.

**Standard recipe (do this exact sequence):**

1. Call `confluence auth init --profile NAME [--site URL] [--email EMAIL] [--space-key KEY]`.
2. Read the `next_steps` array from the JSON envelope. Forward those
   instructions to the user verbatim. Do not try to fill in the token
   yourself.
3. Wait for the user to confirm they've saved the file.
4. Call `confluence auth status --profile NAME` to verify.

For CI / headless contexts, prefer the env-var path — no `auth init`
needed:

```bash
export CONFLUENCE_SITE=https://acme.atlassian.net
export CONFLUENCE_EMAIL=me@acme.com
export CONFLUENCE_TOKEN=...     # CI secret
export CONFLUENCE_SPACE_KEY=DEV
confluence spaces
```

See [references/auth.md](references/auth.md) for the threat model, full
resolution precedence, and the advanced OS-keyring path.

## Publishing a richdoc bundle

Always a two-step flow. The agent should pipe `nextStep.argv` from the
richdoc envelope directly into the next command — don't reconstruct
the bundle path by hand.

```bash
# 1. In the richdoc skill: build the bundle (no credentials needed).
richdoc export confluence docs/ -o build/confluence-docs
# Envelope contains: "nextStep": {"argv": ["confluence", "publish-bundle", "<path>"], ...}

# 2. Here: publish it.
confluence publish-bundle build/confluence-docs --profile work --parent-id 12345
```

The publisher is idempotent: re-running updates existing pages in
place (matched by `(space, parent, title)`) and re-uploads only
changed attachments. Cross-page links and attachment references are
resolved post-creation. See
[references/richdoc-bundles.md](references/richdoc-bundles.md).

### Common agent mistakes

- **Do not** pass a `.html` file or a richdoc source directory to
  `confluence publish-bundle`. It will fail with `code: NOT_A_BUNDLE`
  and a hint pointing at `richdoc export confluence`. Always build a
  bundle first.
- **Do not** attempt to run `auth login` — the command no longer
  exists. Use `auth init` to template a config file, then ask the user
  to fill in the token.
- **Do not** echo, log, or include `CONFLUENCE_TOKEN` or any literal
  token value in commands you suggest to the user. Reference env vars
  by name only.

## Output

Every command writes a single-line JSON envelope to stdout. On
success: `{"ok": true, ...}`. On failure: `{"ok": false, "code": "...",
"error": "...", "hint": "..."}`. Exit code matches.

## Limits and trust

- **Confluence Cloud only.** The v2 REST API the client targets does
  not exist on Data Center.
- **Pages and attachments only.** Whiteboards, databases, blog posts,
  comments, and labels are not managed by this CLI yet.
- **No content sync back from Confluence.** Push only.
- **Destructive operations require confirmation.** `page delete` (when
  implemented) takes `--confirm`; without it the call errors with
  `CONFIRMATION_REQUIRED`.

## See also

- [references/auth.md](references/auth.md) — profile / env / keyring precedence.
- [references/richdoc-bundles.md](references/richdoc-bundles.md) — bundle schema and publish algorithm.
- `richdoc/SKILL.md` — authoring polished HTML documents and producing Confluence bundles.
