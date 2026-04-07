# PostgreSQL Tool Setup

## Configuration

Create a `.pgtool.json` file in the project root.

### Multi-Profile Format (Recommended)

```json
{
  "profiles": {
    "dev": {
      "host": "localhost",
      "port": 5432,
      "database": "myapp_dev",
      "user": "postgres",
      "passwordEnv": "DEV_PG_PASSWORD"
    },
    "staging": {
      "host": "staging-db.internal",
      "database": "myapp",
      "user": "readonly",
      "passwordEnv": "STAGING_PG_PASSWORD",
      "readOnly": true
    },
    "prod": {
      "host": "prod.internal",
      "database": "myapp",
      "user": "ops_readonly",
      "passwordEnv": "PROD_PG_PASSWORD",
      "ssl": { "rejectUnauthorized": true, "ca": "/path/to/ca.pem" },
      "readOnly": true,
      "protected": true
    }
  },
  "default": "dev"
}
```

### URL-Based Profile

```json
{
  "profiles": {
    "cloud": {
      "url": "postgres://user:pass@host:5432/db?sslmode=require",
      "readOnly": true
    }
  }
}
```

A profile uses **either** `url` **or** individual fields (`host`, `database`, `user`, `password`/`passwordEnv`). They cannot be combined.

### Legacy Format (Still Supported)

```json
{
  "host": "localhost",
  "port": 5432,
  "database": "mydb",
  "user": "postgres",
  "passwordEnv": "PGPASSWORD",
  "schema": "public"
}
```

Legacy format is treated as a single profile named "default".

## Profile Fields

### Connection Fields (Field-Based)

| Field         | Required | Description                              |
| ------------- | -------- | ---------------------------------------- |
| `host`        | Yes      | Database hostname                        |
| `port`        | No       | Port (default: 5432)                     |
| `database`    | Yes      | Database name                            |
| `user`        | Yes      | Username                                 |
| `password`    | One of   | Direct password                          |
| `passwordEnv` | One of   | Environment variable containing password |

### Connection Fields (URL-Based)

| Field | Required | Description                                       |
| ----- | -------- | ------------------------------------------------- |
| `url` | Yes      | PostgreSQL connection URL (`postgres://...`)       |

### Common Fields

| Field       | Required | Description                                                    |
| ----------- | -------- | -------------------------------------------------------------- |
| `schema`    | No       | Default schema (default: `public`)                             |
| `ssl`       | No       | `true` or `{ rejectUnauthorized, ca, cert, key }`              |
| `readOnly`  | No       | Enforce read-only mode (PostgreSQL rejects writes)             |
| `protected` | No       | Require human GUI approval before connecting (see below)       |

### Top-Level Fields

| Field     | Required | Description                          |
| --------- | -------- | ------------------------------------ |
| `profiles`| Yes      | Object mapping profile names to configs |
| `default` | No       | Default profile name                 |

## Profile Selection

Priority: `--profile` flag > `PGTOOL_PROFILE` env var > `"default"` field > first profile

```bash
pgtool -p staging tables              # Explicit profile
PGTOOL_PROFILE=staging pgtool tables  # Environment variable
pgtool tables                         # Uses default profile
```

## Read-Only Mode

Profiles with `"readOnly": true` enforce read-only at the PostgreSQL session level. Any write operation (INSERT, UPDATE, DELETE, CREATE, DROP) is rejected by the database.

CLI overrides:
```bash
pgtool --read-only query "SELECT 1"    # Force read-only on any profile
pgtool --allow-writes query "UPDATE …" # Override read-only (not allowed on protected profiles)
```

## Protected Profiles

Profiles with `"protected": true` require human approval via an OS-native GUI dialog before the agent can connect. The dialog appears on the user's desktop — the agent cannot interact with it.

- **Linux**: zenity dialog
- **macOS**: AppleScript dialog
- **Windows 11**: PowerShell MessageBox

Approval is cached for the daemon session (expires when daemon auto-stops after 5 minutes idle). Protected profiles require the daemon — they cannot use direct connections.

## Connection Daemon

The daemon is a background process that maintains connection pools across CLI calls, eliminating per-call connection overhead.

- **Auto-starts** on the first CLI call
- **Auto-stops** after 5 minutes of inactivity
- **System-wide**: one daemon per OS user, shared across projects

```bash
pgtool daemon start    # Explicitly start
pgtool daemon stop     # Stop the daemon
pgtool daemon status   # Show status and pool info
```

Disable with `PGTOOL_NO_DAEMON=1` (non-protected profiles only).

## Config Integrity

The daemon monitors `.pgtool.json` for modifications. If security-relevant changes are detected (removal of `readOnly` or `protected` flags), a GUI dialog asks the human to accept or reject the changes. Rejected changes are ignored — the daemon continues using the original config.

## Error Codes

All errors return JSON with `ok: false`:

```json
{
  "ok": false,
  "error": "Table not found",
  "code": "TABLE_NOT_FOUND",
  "hint": "Check that the table exists. Use 'pgtool tables' to list available tables."
}
```

| Code | Description |
|------|-------------|
| `CONFIG_NOT_FOUND` | `.pgtool.json` not found |
| `CONFIG_INVALID` | Invalid config format or missing fields |
| `CONFIG_TAMPERED` | Config modified and change was rejected |
| `CONNECTION_FAILED` | Cannot connect to database |
| `QUERY_FAILED` | SQL error |
| `TABLE_NOT_FOUND` | Table does not exist |
| `SCHEMA_NOT_FOUND` | Schema does not exist |
| `PERMISSION_DENIED` | Auth failed or insufficient privileges |
| `TIMEOUT` | Query timed out |
| `READ_ONLY` | Write blocked on read-only connection |
| `PROTECTED_DENIED` | Protected profile not approved |
