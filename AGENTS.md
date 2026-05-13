# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

A collection of reusable AI agent skills.

| Skill | Purpose |
|-------|---------|
| `droid/` | Android device automation via ADB (TypeScript CLI) |
| `pgtool/` | PostgreSQL database exploration and debugging |
| `imagegen/` | AI image generation via Google Gemini |
| `playbook/` | Create and refine repo-specific `AGENTS.md` files |
| `richdoc/` | Framework for AI-authored HTML documents — fixed `rd-*` web-component vocabulary, modular sources, build pipeline |

## Skill Structure

```
skill-name/
├── SKILL.md              # Skill definition
├── skill-name-cli/       # Optional CLI tool (Bun + citty)
│   ├── src/
│   │   ├── index.ts      # Entry point (citty framework)
│   │   ├── commands/     # Command definitions
│   │   ├── lib/          # Core libraries
│   │   └── types/        # TypeScript types
│   ├── package.json
│   ├── biome.json
│   └── skill-name        # Shell entry script
├── references/           # Optional extra docs
└── SETUP.md              # Optional setup guide
```

Some skills are documentation-only and only need `SKILL.md` (for example `playbook/`).

## CLI Development

CLI-backed skills follow the same pattern:

```bash
cd droid/droid-cli && bun install       # droid-cli
cd pgtool/pgtool-cli && bun install     # pgtool-cli
cd imagegen/imagegen-cli && bun install  # imagegen-cli
cd richdoc/richdoc-cli && bun install    # richdoc-cli
bun run dev [command]           # Run in development
bun run lint                    # Check with Biome
bun run lint:fix                # Auto-fix lint issues
bun run format                  # Format with Biome
```

## CLI Global Options

All CLIs output JSON by default. Common options:
- `--plain` - Human-readable output instead of JSON
- `--root, -r <path>` - Project root directory (default: auto-detect)
- `--quiet, -q` - Minimal output (available on most commands)

## droid-cli Commands

| Command | Description |
|---------|-------------|
| `droid screenshot` | Capture screenshot + UI elements |
| `droid tap` | Tap by text or coordinates |
| `droid fill <field> <text>` | Fill text field |
| `droid wait-for -t <text>` | Wait for element |
| `droid clear` | Clear focused field |
| `droid type <text>` | Type into focused field |
| `droid key <keyname>` | Send key event |
| `droid swipe <direction>` | Swipe gesture |
| `droid longpress` | Long press |
| `droid launch <package>` | Launch app |
| `droid current` | Current activity |
| `droid info` | Device info |
| `droid wait <ms>` | Wait milliseconds |
| `droid select-all` | Select text |
| `droid hide-keyboard` | Dismiss keyboard |

### droid-cli Architecture

**Entry:** `src/index.ts` uses citty framework.

**Commands (`src/commands/`):** Each file exports a citty command definition.

**Core Libraries (`src/lib/`):**
- `adb.ts` - ADB command execution
- `ui-hierarchy.ts` - UI dump parsing
- `ui-element.ts` - Element finding and matching
- `keycodes.ts` - Android keycode mappings
- `output.ts` - JSON output formatting

## pgtool-cli Commands

Requires `.pgtool.json` config file with connection details.

| Command | Description |
|---------|-------------|
| `pgtool schemas` | List database schemas |
| `pgtool tables [schema]` | List tables |
| `pgtool describe <table>` | Show columns with PK/FK info |
| `pgtool indexes <table>` | List table indexes |
| `pgtool constraints <table>` | List constraints |
| `pgtool relationships [schema]` | Show FK relationships |
| `pgtool query <sql>` | Execute SQL query |
| `pgtool sample <table>` | Sample rows from table |
| `pgtool count <table>` | Count rows |
| `pgtool search <term>` | Search across tables |
| `pgtool overview` | Database overview |
| `pgtool explain <sql>` | Explain query plan |

### pgtool-cli Architecture

**Entry:** `src/index.ts` uses citty framework.

**Core Libraries (`src/lib/`):**
- `config.ts` - Reads `.pgtool.json`
- `connection.ts` - PostgreSQL pool management
- `project-root.ts` - Finds config file
- `output.ts` - JSON/plain formatting
- `init.ts` - Initialization utilities

## imagegen-cli Commands

Requires a Gemini API key, resolved in order: `GEMINI_API_KEY` env var → `.gemini-key` file walked up from CWD → `~/.gemini-key`. Targets the Gemini Nano Banana 2 family (`gemini-3.1-flash-image-preview` by default).

| Command | Description |
|---------|-------------|
| `imagegen generate <prompt>` | Generate or edit an image (pass `--image` to edit/compose) |
| `imagegen gen <prompt>` | Alias for generate |

Options: `--output/-o`, `--image/-i` (repeatable), `--aspect-ratio/-a`, `--size/-s` (`512`/`1K`/`2K`/`4K`), `--thinking/-t` (`minimal`/`high`), `--negative-prompt/-n`, `--model/-m`. Run `imagegen generate --help` for current values; flag validity is model-dependent.

### imagegen-cli Architecture

**Entry:** `src/index.ts` uses citty framework.

**Core Libraries (`src/lib/`):**
- `output.ts` - JSON output formatting
- `models.ts` - Per-model capability matrix (sizes, aspect ratios, thinking, max input images)
- `inputs.ts` - Reads & base64-encodes local image files for editing/composition
- `api-key.ts` - Resolves the Gemini API key from env, project `.gemini-key` (walked up from CWD), or `~/.gemini-key`

**Commands (`src/commands/`):**
- `generate.ts` - Unified text-to-image and image-edit command

## richdoc framework

Documents are plain `.html` files that link two shipped assets (`richdoc.css`, `richdoc.js`) and use the `rd-*` web-component vocabulary. Source is modular (one folder per component), built into a single minified CSS/JS bundle plus a generated `schema.json`.

### Layout

```
richdoc/
├── SKILL.md, AUTHORING.md
├── src/                          # framework source
│   ├── lib/{base,types}.ts
│   ├── styles/{tokens,reset,typography,print,index}.css
│   ├── components/<name>/{<name>.ts, <name>.css, <name>.schema.ts}
│   ├── registry.ts                # browser-side component registrations
│   └── schema-registry.ts         # pure schema, no DOM (Node-safe)
├── build.ts                       # bun-powered bundler
├── assets/                        # GENERATED, committed
│   ├── richdoc.css, richdoc.js     # minified bundles + .map
│   ├── schema.json                 # vocabulary, consumed by CLI lint
│   └── version.txt                 # bundle hash + build timestamp
├── templates/                     # plan, research, comparison
├── examples/                      # showcase, status-onepager
└── richdoc-cli/
```

### Build pipeline

```bash
cd richdoc
bun install
bun run build              # production: minified, source maps
bun run build:dev          # unminified
```

The build emits `assets/{richdoc.js, richdoc.css, schema.json, version.txt}`, then sanity-checks `examples/showcase.html` against the freshly generated schema. Builds are reproducible: same source produces byte-identical `richdoc.js`, `richdoc.css`, and `schema.json` (only `version.txt`'s timestamp varies).

Adding a new component: drop `src/components/<name>/{<name>.ts, <name>.css, <name>.schema.ts}`, edit `src/registry.ts`, `src/schema-registry.ts`, and `src/styles/index.css` (one line each), run `bun run build`. See `richdoc/AUTHORING.md`.

### richdoc-cli Commands

| Command | Description |
|---------|-------------|
| `richdoc new <output>` | Scaffold from a template (`--template plan\|research\|comparison`) |
| `richdoc init [dir]` | Copy `richdoc.css` and `richdoc.js` into a directory |
| `richdoc lint <file>` | Validate against the rd-* schema (loads `assets/schema.json`) |
| `richdoc components [--tag <name>] [--plain]` | List the vocabulary from the live schema |
| `richdoc build [--dev]` | Rebuild the bundle (wraps `bun run build`) |

### richdoc-cli Architecture

**Entry:** `src/index.ts` uses citty framework.

**Core Libraries (`src/lib/`):**
- `output.ts` - JSON output formatting
- `assets.ts` - Resolves shipped `assets/richdoc.css` and `assets/richdoc.js`
- `templates.ts` - Resolves shipped `templates/*.html`
- `schema.ts` - Loads `assets/schema.json` at runtime; single source of truth for the rd-* tag vocabulary

**Commands (`src/commands/`):**
- `new.ts` - Scaffold from template
- `init.ts` - Copy assets into a target dir
- `lint.ts` - Parse HTML and validate against the loaded schema
- `components.ts` - Print the vocabulary (JSON or `--plain` table)
- `build.ts` - Spawn `bun run build.ts` from the framework root
