# confluence-cli

Agent-facing CLI for Confluence Cloud. Manages spaces, pages, attachments,
auth/profile storage, **downloading existing pages locally** (JSONL +
optional markdown), and publishing `richdoc.confluence.bundle.v1`
bundles produced by `richdoc export confluence`.

Quick examples:

```bash
# Download one page (URL or id; tinylinks must be expanded first).
confluence download "https://acme.atlassian.net/wiki/spaces/DEV/pages/123/T" -o ./pulled

# Subtree + markdown + attachments.
confluence download 123 -o ./pulled --recurse --markdown --attachments

# Edit the storage XML extracted from pages.jsonl, then push it back.
confluence page update 123 --body-file edited.storage.xml
```

- See the parent skill: [`../SKILL.md`](../SKILL.md).
- Requires `uv` ([install](https://docs.astral.sh/uv/)). First call provisions the Python environment automatically.
- Output is JSON on every command (success and error). Built for AI agents, not humans.

## Source layout

```
src/confluence_cli/
  cli.py              # click group + JSON-safe error trap
  output.py           # json_ok / json_error envelopes
  client.py           # stdlib REST client (urllib + email.mime multipart)
  auth.py             # profile / env / keyring credential resolution
  config.py           # project + user config files
  bundle.py           # read richdoc.confluence.bundle.v1
  publish.py          # bundle → Confluence pages + attachments
  commands/           # click subcommand modules
    auth.py           #   confluence auth init|profiles|use|logout|status
    spaces.py         #   confluence spaces
    pages.py          #   confluence pages / page get|create|update|delete
    publish_bundle.py #   confluence publish-bundle
    download.py       #   confluence download (page → JSONL + optional markdown)
  refs.py             # parse page ids / URLs / ?pageId= query strings
  markdown.py         # best-effort storage XML → markdown
  tls.py              # shared SSL context (corporate CA bundle env vars)
```

## Behind a corporate TLS proxy

If you sit behind a TLS-intercepting proxy (Netskope, Zscaler, Palo
Alto, …) the CLI honors the same CA-bundle env vars `curl` /
`requests` honor, in this precedence order:

1. `CONFLUENCE_CA_BUNDLE` — CLI-specific override.
2. `SSL_CERT_FILE` — stdlib-standard.
3. `REQUESTS_CA_BUNDLE` — what `requests` honors.
4. `CURL_CA_BUNDLE` — what `curl` honors.

As a last-resort triage knob, `CONFLUENCE_INSECURE=1` disables
certificate verification entirely (loud stderr warning; do not use in
production). Run `confluence auth status` to see which bundle was
loaded; see [`../references/auth.md`](../references/auth.md) for the
full explanation.

## Development

```bash
uv sync --extra dev
uv run ruff check src
```
