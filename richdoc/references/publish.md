# `richdoc confluence` has moved

Confluence publishing is no longer part of the `richdoc` skill. The
two responsibilities have been split:

- **Authoring + offline bundle** stays here. Use
  `richdoc export confluence <input> -o <bundle-dir>` to produce a
  `richdoc.confluence.bundle.v1` directory (storage XML + attachments +
  manifest). No Confluence credentials are needed at this stage. See
  [references/export.md](export.md).

- **Confluence content management + bundle publishing** moved to a
  dedicated `confluence` skill. It owns auth/profile handling
  (env vars, project `.confluence.json`, user config, OS keyring),
  the REST client, page/space management commands, and the
  `confluence publish-bundle` two-pass publisher.

## Migration

Before:

```bash
export CONFLUENCE_SITE=https://acme.atlassian.net
export CONFLUENCE_EMAIL=me@acme.com
export CONFLUENCE_TOKEN=...
export CONFLUENCE_SPACE_KEY=DEV
richdoc confluence publish docs/ --parent-id 12345
```

After:

```bash
# One-time setup: template a config file. The CLI writes a
# `<your-token-here>` placeholder; the human user opens the file in
# their editor and pastes the real Atlassian API token.
confluence auth init \
  --profile work \
  --site https://acme.atlassian.net \
  --email me@acme.com \
  --space-key DEV
# (User edits ~/.config/confluence-cli/config.json and saves.)

# Per publish:
richdoc export confluence docs/ -o build/confluence-docs
confluence publish-bundle build/confluence-docs --profile work --parent-id 12345
```

The env-var path still works for CI/agent contexts — set
`CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`, `CONFLUENCE_TOKEN`, and
`CONFLUENCE_SPACE_KEY` and skip `auth init`.

See `confluence/SKILL.md` and
`confluence/references/{auth,richdoc-bundles}.md` for the full
reference on the new skill.
