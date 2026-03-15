# codex

OpenAI Codex CLI plugin for Claude Code — get second opinions, delegate research, and run code reviews.

## Setup

1. Install the Codex CLI: https://github.com/openai/codex
2. Log in to the Codex CLI:
   ```bash
   codex auth login
   ```
   This works with either a ChatGPT subscription or an OpenAI API key.
3. Install the plugin:
   ```bash
   /plugin marketplace add /path/to/claude-plugins
   /plugin install codex@tlmtech
   ```

## Usage

Ask Claude to use Codex naturally:

- "Ask codex to review this file for security issues"
- "Get a second opinion on the auth flow"
- "Run codex to research how to implement caching here"
- "Codex review the changes in src/api/"

Codex runs in read-only mode by default. For tasks that need file writes (e.g. generating tests), it switches to workspace-write mode automatically.
