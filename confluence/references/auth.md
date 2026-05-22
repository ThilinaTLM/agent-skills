# confluence — authentication & profile reference

The `confluence` skill talks to Confluence Cloud over HTTP Basic with
`email:api_token`. This document explains how the CLI gets the token,
what the security guarantees are, and how the AI-agent-driven setup
flow works.

## Security model (what this CLI defends against)

**Adversary.** The CLI assumes it runs under an AI agent that has
shell access to the user's machine. The agent can read its own
subprocess stdout/stderr, read env vars, see command arguments, and
read any file the user can read.

**What the CLI guarantees.**

- It never accepts an API token as a flag value (`--token` does not
  exist), on stdin, or via any channel the AI agent controls.
- It never prints a resolved token in command output (success or
  error envelopes).
- It never logs the token, including under `--verbose` modes.
- The placeholder string `<your-token-here>` left in a freshly-templated
  config file is rejected as a real token, so a half-completed setup
  fails closed with `CONFIG_MISSING`.

**What the CLI does NOT defend against.**

- A malicious agent that `cat`s the config file. The token, once the
  user pastes it, is plaintext on disk under file mode `0600`
  (POSIX) or the user-profile NTFS ACLs (Windows). This is the same
  trade-off `aws configure`, `gh auth`, and `kubectl` make.
- An adversary that has already obtained root / `ptrace` privileges.
- An agent that `echo $CONFLUENCE_TOKEN` when the env var is set.
  Users who care should keep the token in the config file or the OS
  keyring, not in their shell environment.

**Stronger boundary (opt-in).** Power users can move the token into
the OS keyring and reference it from the config; see the *Advanced*
section below. `confluence auth status --strict` requires this and
exits non-zero otherwise.

## Where the config file lives

| OS      | Path                                                        |
| ------- | ----------------------------------------------------------- |
| Linux   | `${XDG_CONFIG_HOME:-~/.config}/confluence-cli/config.json`  |
| macOS   | `~/.config/confluence-cli/config.json`                      |
| Windows | `%APPDATA%\confluence-cli\config.json`                      |

On POSIX the file is written with mode `0600` (owner read/write only).
On Windows it inherits the default `%APPDATA%` ACLs, which are
owner-only by default; the CLI does not attempt to set NTFS ACLs
explicitly.

## Credential resolution order

For every command, credentials are resolved by walking these sources
in order. The first match wins for each non-secret field.

1. **Explicit command flags.** `--site`, `--email`, `--token-env`,
   `--space-key`, `--parent-id`, `--profile`. There is deliberately
   no `--token` flag.
2. **Environment variables.** `CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`,
   `CONFLUENCE_TOKEN`, `CONFLUENCE_SPACE_KEY`, `CONFLUENCE_PROFILE`.
3. **Project config.** `.confluence.json` walked upward from cwd.
4. **User config.** The path in the table above.

Token-specific precedence (after the non-secret walk):

1. `--token-env NAME` flag → reads `$NAME`.
2. `CONFLUENCE_TOKEN` env var.
3. Profile `tokenEnv` (project then user) → reads the named env var.
4. Profile `token` literal (project then user). The placeholder
   `<your-token-here>` is treated as "not set".
5. Profile `tokenRef` (user then project) → keyring lookup. Lazy
   import; missing `keyring` package is a soft fail.

If no token can be resolved, the CLI exits with `code: CONFIG_MISSING`
and `missing: ["token", ...]`. There is no interactive prompt.

## The AI-agent setup workflow

The CLI is designed to be driven entirely by an AI agent. The agent's
job is to template the config file and then forward natural-language
instructions to the human user, who is the one entering the token.

```bash
confluence auth init --profile work \
  --site https://acme.atlassian.net \
  --email me@acme.com \
  --space-key DEV
```

The envelope contains `next_steps[]` — an array of plain-English
strings the agent should forward to the user verbatim:

```json
{
  "ok": true,
  "profile": "work",
  "config": "/home/user/.config/confluence-cli/config.json",
  "tokenSource": "file-placeholder",
  "next_steps": [
    "Open /home/user/.config/confluence-cli/config.json in your editor.",
    "Replace \"<your-token-here>\" with your real Atlassian API token, then save.",
    "Verify with: confluence auth status --profile work",
    "Generate a token at https://id.atlassian.com/manage-profile/security/api-tokens."
  ]
}
```

After the user saves the file:

```bash
confluence auth status --profile work
```

reports `secure: false` (plaintext file storage) along with a
`secureNotes` array explaining why. That's the **expected** default;
file storage is the standard trade-off. `secure: true` is reserved
for the keyring path described below.

## Sample config files

### User config (`~/.config/confluence-cli/config.json`)

```json
{
  "defaultProfile": "work",
  "profiles": {
    "work": {
      "site": "https://acme.atlassian.net",
      "email": "me@acme.com",
      "spaceKey": "DEV",
      "token": "atlassian-api-token-pasted-by-the-user"
    },
    "ci": {
      "site": "https://acme.atlassian.net",
      "email": "ci@acme.com",
      "spaceKey": "DEV",
      "tokenEnv": "ACME_CONFLUENCE_TOKEN"
    },
    "personal": {
      "site": "https://me.atlassian.net",
      "email": "me@example.com",
      "tokenRef": "keyring:confluence-cli/personal|me.atlassian.net|me@example.com"
    }
  }
}
```

### Project config (`.confluence.json`, optional, committable)

```json
{
  "defaultProfile": "work",
  "profiles": {
    "work": {
      "site": "https://acme.atlassian.net",
      "spaceKey": "DEV",
      "parentId": "1234567",
      "tokenEnv": "CONFLUENCE_TOKEN"
    }
  }
}
```

> **Caution:** the project config schema also accepts a literal `token`
> field for consistency with the user config. **Do not commit it.** Add
> `.confluence.json` to your `.gitignore` if your project file may
> contain a real token; or keep tokens out of project configs entirely
> and use `tokenEnv` instead.

## CI / scripted use

For CI, skip `auth init` entirely. Set the env vars from CI secrets:

```bash
export CONFLUENCE_SITE=https://acme.atlassian.net
export CONFLUENCE_EMAIL=ci@example.com
export CONFLUENCE_TOKEN=$CI_ATLASSIAN_TOKEN
export CONFLUENCE_SPACE_KEY=DEV
confluence publish-bundle build/confluence-docs --parent-id 12345
```

Or use a named env var via `--token-env`:

```bash
confluence publish-bundle build/confluence-docs \
  --site https://acme.atlassian.net \
  --email ci@example.com \
  --space-key DEV \
  --token-env CI_ATLASSIAN_TOKEN \
  --parent-id 12345
```

## Advanced: storing the token in the OS keyring

For users who want a stronger boundary than a plaintext file. The CLI
**reads** keyring entries but does not **write** them; you set them up
yourself with your OS's keyring tool.

### Linux (GNOME / libsecret)

```bash
secret-tool store \
  --label="Confluence (work)" \
  service confluence-cli \
  account "work|acme.atlassian.net|me@acme.com"
# Prompts for the token; press Ctrl-D after pasting.
```

### macOS

```bash
security add-generic-password \
  -s confluence-cli \
  -a "work|acme.atlassian.net|me@acme.com" \
  -w
# Prompts for the token.
```

### Windows

Use the Credential Manager UI ("Generic Credentials" → Add) with
Internet/Network address `confluence-cli` and User name
`work|acme.atlassian.net|me@acme.com`.

### Point the profile at the keyring

In your `confluence-cli/config.json`, replace the literal `token`
field with `tokenRef`:

```json
"work": {
  "site": "https://acme.atlassian.net",
  "email": "me@acme.com",
  "spaceKey": "DEV",
  "tokenRef": "keyring:confluence-cli/work|acme.atlassian.net|me@acme.com"
}
```

The CLI lazy-imports the `keyring` Python package only when this path
is taken. Install it on demand:

```bash
uv pip install --project confluence/confluence-cli keyring
```

`confluence auth status --profile work` will then report
`tokenSource: "user:keyring"` and `secure: true`.

## Command reference

### `confluence auth init`

```
confluence auth init --profile NAME
                     [--site URL] [--email EMAIL]
                     [--space-key KEY] [--parent-id ID]
                     [--token-env NAME] [--force]
```

Writes a profile to the user config. By default the `token` field is
filled with the placeholder `<your-token-here>`. With `--token-env`,
no placeholder is written — the named env var is read at runtime.

The agent must forward the returned `next_steps` array to the user
verbatim; the CLI's protection rests on the user being the one to
paste the token.

### `confluence auth profiles`

Lists configured profiles from project and user configs. Token values
never appear. The `tokenSource` field is one of `keyring`, `env`,
`file`, `file-placeholder`, or `null`.

### `confluence auth use PROFILE`

Sets `defaultProfile` in the user config.

### `confluence auth status [--profile NAME] [--strict] [--no-verify]`

Resolves credentials end-to-end. Reports:

- `sources.token` — resolver label (e.g. `user:file`, `env:CONFLUENCE_TOKEN`).
- `tokenLocation` — user-friendly path or env-var name. Never the
  token value.
- `secure` — `true` only when the token came from the keyring AND
  `CONFLUENCE_TOKEN` is not set in the environment.
- `secureNotes[]` — explanation when `secure` is `false`.
- `reachable` — `true` when the read-only probe succeeded. Skip with
  `--no-verify`.

With `--strict`, exits non-zero when `secure` is `false`. Agent
harnesses can use this at session start to refuse to operate against
a plaintext-file token.

### `confluence auth logout --profile NAME [--keep-config]`

Removes the profile entry from the user config (default) or just
clears the token fields (`--keep-config`). Does **not** delete
keyring entries — the CLI never owned them.

## Error codes

| Code | Cause |
|---|---|
| `CONFIG_MISSING` | One or more required credential fields could not be resolved. The envelope's `missing[]` lists them. |
| `AUTH_ERROR` | Site URL malformed, or Confluence rejected the credentials at the read-only probe. |
| `AUTH_INSECURE` | `auth status --strict` and `secure: false`. |
| `INVALID_PARAMS` | Malformed config (bad JSON or wrong shape). |
| `FILE_EXISTS` | `auth init` would overwrite an existing profile without `--force`. |
| `NOT_FOUND` | `auth use` / `auth logout` targeted a profile that does not exist. |
