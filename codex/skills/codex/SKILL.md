---
name: codex
description: This skill should be used when the user asks to "run codex", "use codex", "ask codex", "get a second opinion", "codex review", "codex research", or wants to delegate a task to OpenAI Codex CLI for an alternative perspective, research, or non-critical implementation.
---

# Codex

OpenAI Codex CLI running non-interactively via `codex exec`. Useful for getting a second perspective, delegating research, code review, or non-critical implementation tasks.

## Base Command

```bash
codex exec --skip-git-repo-check --ephemeral -s <sandbox> -o /tmp/codex-output.txt "<prompt>"
```

Always include:

- `--skip-git-repo-check` — required, project may not be a git repo
- `--ephemeral` — no session persistence needed
- `-o /tmp/codex-output.txt` — capture output for reading back with Read tool

After execution, read `/tmp/codex-output.txt` with the Read tool to get Codex's response.

## Sandbox Selection

| Task Type                             | Sandbox         | Flag                 |
| ------------------------------------- | --------------- | -------------------- |
| Research, review, planning, analysis  | Read-only       | `-s read-only`       |
| Implementation, file creation/editing | Workspace-write | `-s workspace-write` |

Default to `read-only`. Only use `workspace-write` when the task explicitly requires file modifications.

## Common Options

| Flag            | Purpose                        | Example               |
| --------------- | ------------------------------ | --------------------- |
| `-s, --sandbox` | Sandbox policy                 | `-s read-only`        |
| `-m, --model`   | Override model                 | `-m o3`               |
| `-C, --cd`      | Working directory              | `-C /path/to/project` |
| `--full-auto`   | Auto-approve + workspace-write | `--full-auto`         |
| `-i, --image`   | Attach image(s)                | `-i screenshot.png`   |

## Workflow Patterns

### Research / Second Opinion

```bash
codex exec --skip-git-repo-check --ephemeral -s read-only -o /tmp/codex-output.txt "Analyze the authentication flow in this project and identify potential issues"
```

### Code Review

```bash
codex exec --skip-git-repo-check --ephemeral -s read-only -o /tmp/codex-output.txt "Review the changes in src/auth/LoginService.java for security issues and suggest improvements"
```

### Non-Critical Implementation

```bash
codex exec --skip-git-repo-check --ephemeral -s workspace-write -o /tmp/codex-output.txt "Create unit tests for the VenueService class in src/venue/VenueService.java"
```

### Planning / Requirements Analysis

```bash
codex exec --skip-git-repo-check --ephemeral -s read-only -o /tmp/codex-output.txt "Read the SRS at docs/release1/SRS.md and outline the implementation steps for the booking module"
```

## Tips

- Provide specific file paths and context in the prompt for better results
- For long-running tasks, use Bash `run_in_background` to avoid blocking
- Review Codex's output before accepting any implementation — treat as suggestions, not final code
- When Codex writes files (workspace-write), review the changes with `git diff` before committing
