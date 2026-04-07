# PostgreSQL Tool Setup

## Configuration

Create a `.pgtool.json` file in the project root:

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

| Field         | Required | Description                              |
| ------------- | -------- | ---------------------------------------- |
| `host`        | Yes      | Database hostname                        |
| `port`        | No       | Port (default: 5432)                     |
| `database`    | Yes      | Database name                            |
| `user`        | Yes      | Username                                 |
| `password`    | One of   | Direct password                          |
| `passwordEnv` | One of   | Environment variable containing password |
| `schema`      | No       | Default schema (default: public)         |

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

Error codes: `CONFIG_NOT_FOUND`, `CONFIG_INVALID`, `CONNECTION_FAILED`, `QUERY_FAILED`, `TABLE_NOT_FOUND`, `SCHEMA_NOT_FOUND`, `PERMISSION_DENIED`, `TIMEOUT`
