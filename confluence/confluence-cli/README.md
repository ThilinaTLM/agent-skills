# confluence-cli

Agent-facing CLI for Confluence Cloud. Manages spaces, pages, attachments,
auth/profile storage, and publishing `richdoc.confluence.bundle.v1`
bundles produced by `richdoc export confluence`.

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
```

## Development

```bash
uv sync --extra dev
uv run ruff check src
```
