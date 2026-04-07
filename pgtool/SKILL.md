---
name: pgtool
description: PostgreSQL database exploration and debugging. Use when user asks to explore database schemas, tables, columns, or run queries. Requires a `.pgtool.json` file in the project directory.
---

# PostgreSQL

A CLI tool for exploring and debugging PostgreSQL databases with JSON-first output designed for AI agents.

## CLI Discovery

The CLI is located at `./pgtool-cli/` relative to this SKILL.md file.

| Platform         | Script       |
| ---------------- | ------------ |
| Unix/Linux/macOS | `pgtool`     |
| Windows          | `pgtool.ps1` |

For setup instructions, see SETUP.md in this directory.

## Important

- **Always use pgtool-cli** for all database operations. Do NOT use `psql` directly.
- If pgtool-cli encounters an error or limitation, report the issue to the user and stop. Do not fall back to psql or other tools.
- Always add `LIMIT` to SELECT queries to avoid fetching excessive data.

## Commands

### List Schemas

```bash
pgtool schemas
```

Output: `{"ok":true,"schemas":[{"name":"public","owner":"postgres"}]}`

### List Tables

```bash
# Tables in default schema
pgtool tables

# Tables in a specific schema
pgtool tables auth
```

Output: `{"ok":true,"schema":"public","tables":[{"name":"users","type":"table","rowEstimate":1000,"sizeHuman":"256 KB"}]}`

### Describe Table

Get column details with primary key and foreign key information.

```bash
# Table in default schema
pgtool describe users

# Table in specific schema
pgtool describe auth.users
```

Output includes column types, nullability, defaults, PK/FK info, and foreign key references.

### List Indexes

```bash
pgtool indexes users
```

Output: `{"ok":true,"indexes":[{"name":"users_pkey","unique":true,"primary":true,"columns":["id"],"type":"btree"}]}`

### List Constraints

```bash
pgtool constraints users
```

Output includes PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK, and EXCLUDE constraints.

### List Relationships

Get all foreign key relationships in a schema.

```bash
pgtool relationships
pgtool relationships auth
```

Output: `{"ok":true,"relationships":[{"fromTable":"orders","fromColumns":["user_id"],"toTable":"users","toColumns":["id"]}]}`

### Execute Query

```bash
pgtool query "SELECT * FROM users WHERE active = true LIMIT 100"
```

Output: `{"ok":true,"rows":[...],"rowCount":5,"fields":["id","name","email"]}`

**Best Practices:**

- Always add `LIMIT` to SELECT queries to avoid fetching excessive data
- DML statements (INSERT, UPDATE, DELETE) with RETURNING are fully supported
- Use parameterized values in WHERE clauses to avoid SQL injection

### Sample Table Rows

Get sample data from a table quickly.

```bash
# Default: 5 rows
pgtool sample users

# Custom limit
pgtool sample users --limit 10

# Specific schema
pgtool sample auth.users
```

Output: `{"ok":true,"schema":"public","table":"users","rows":[...],"rowCount":5,"columns":["id","name","email"]}`

### Count Table Rows

Get exact row count (not estimate).

```bash
pgtool count users
pgtool count auth.sessions
```

Output: `{"ok":true,"schema":"public","table":"users","count":12345}`

Plain: `public.users: 12,345 rows`

### Search Tables and Columns

Find tables and columns matching a pattern.

```bash
pgtool search email
pgtool search user
```

Output:

```json
{
  "ok": true,
  "pattern": "email",
  "matches": {
    "tables": [{ "schema": "public", "name": "emails" }],
    "columns": [
      {
        "schema": "public",
        "table": "users",
        "column": "email",
        "type": "varchar(255)"
      },
      {
        "schema": "public",
        "table": "contacts",
        "column": "email_address",
        "type": "text"
      }
    ]
  }
}
```

### Schema Overview

Compact ERD-like view showing tables, primary keys, and relationships.

```bash
pgtool overview
pgtool overview auth
```

Output (plain):

```
Schema: public (3 tables)

users (1.2k rows)
  PK: id
  → orders.user_id, profiles.user_id

orders (45k rows)
  PK: id
  FK: user_id → users.id
  → order_items.order_id

products (500 rows)
  PK: id
```

### Explain Query Plan

Analyze query execution plan.

```bash
# With ANALYZE (executes query)
pgtool explain "SELECT * FROM users WHERE email = 'x'"

# Without ANALYZE (plan only)
pgtool explain "SELECT * FROM users WHERE id = 1" --no-analyze
```

Output: `{"ok":true,"query":"SELECT...","plan":["Seq Scan on users...","..."]}`

## Error Responses

All errors follow a consistent JSON format with `ok: false`, an error code, and a helpful hint:

**Configuration not found:**

```json
{
  "ok": false,
  "error": "Configuration file not found",
  "code": "CONFIG_NOT_FOUND",
  "hint": "Create a .pgtool.json file in your project root with database connection details."
}
```

**Connection failed:**

```json
{
  "ok": false,
  "error": "Could not connect to database server: connect ECONNREFUSED 127.0.0.1:5432",
  "code": "CONNECTION_FAILED",
  "hint": "Verify host and port in .pgtool.json and ensure PostgreSQL is running"
}
```

**Authentication failed:**

```json
{
  "ok": false,
  "error": "Authentication failed",
  "code": "PERMISSION_DENIED",
  "hint": "Check your username and password in .pgtool.json"
}
```

**Table not found:**

```json
{
  "ok": false,
  "error": "relation \"nonexistent_table\" does not exist",
  "code": "TABLE_NOT_FOUND",
  "hint": "Check that the table exists and you have permission to access it"
}
```

**Error codes:** `CONFIG_NOT_FOUND`, `CONFIG_INVALID`, `CONNECTION_FAILED`, `QUERY_FAILED`, `TABLE_NOT_FOUND`, `SCHEMA_NOT_FOUND`, `PERMISSION_DENIED`, `TIMEOUT`

## Common Usage Patterns

**Exploring a new database:**

1. `pgtool schemas` - See available schemas
2. `pgtool overview` - Quick view of tables and relationships
3. `pgtool tables <schema>` - List tables with sizes
4. `pgtool describe <table>` - Understand table structures
5. `pgtool sample <table>` - See example data

**Finding data:**

1. `pgtool search <pattern>` - Find tables/columns by name
2. `pgtool sample <table>` - Quick data preview
3. `pgtool count <table>` - Get exact row count
4. `pgtool query "SELECT..."` - Custom queries

**Debugging data issues:**

1. `pgtool describe <table>` - Verify column types
2. `pgtool sample <table>` - Check actual data
3. `pgtool explain "SELECT..."` - Analyze query performance
4. `pgtool indexes <table>` - Check index coverage

**Understanding relationships:**

1. `pgtool overview` - Visual relationship map
2. `pgtool relationships` - Get all FK relationships
3. `pgtool constraints <table>` - See specific table constraints
