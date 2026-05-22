# Agent Skills

Reusable AI agent skills — drop a skill directory into your project and your agent gains new capabilities.

## Available Skills

| Skill                      | Description                                                                                                                                                                                                            |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [droid](./droid)           | Android device and emulator automation over ADB — tap, swipe, type, screenshot, dump UI, and validate app flows. Unified CLI with JSON output optimized for LLM consumption.                                           |
| [pgtool](./pgtool)         | PostgreSQL exploration and debugging — inspect schemas, tables, columns, indexes, and run ad-hoc queries. JSON-first CLI driven by a per-project `.pgtool.json` config.                                                |
| [imagegen](./imagegen)     | Text-to-image generation and image editing backed by Google Gemini (Nano Banana 2). Create covers, illustrations, logos, banners, thumbnails, or restyle and compose existing images. JSON output.                     |
| [diagram](./diagram)       | Render text-based diagrams (PlantUML, Mermaid, GraphViz, D2, DBML, BPMN, C4, Erd, Ditaa, Nomnoml, Pikchr, Structurizr, SvgBob, TikZ, Vega/Vega-Lite, WaveDrom, BlockDiag family, …) to SVG/PNG/PDF/JPEG via Kroki.      |
| [playbook](./playbook)     | Author, audit, and trim repo-specific `AGENTS.md` files. Produces compact, LLM-optimized instruction files derived from the actual codebase, plus optional authoring guidance.                                         |
| [richdoc](./richdoc)       | Author polished, browser-ready HTML deliverables — research reports, design docs, one-pagers, decision docs, dashboards — using a fixed vocabulary of `rd-*` web components. Ships a CLI for scaffolding and validation. |
| [confluence](./confluence) | Manage Confluence Cloud from the CLI — list/search spaces, create/update/delete pages, upload attachments, manage auth profiles, and publish richdoc-generated storage bundles. JSON output, no interactive prompts.   |

## Installation

### Install with the skills.sh CLI

Use the [`skills`](https://skills.sh/docs/cli) CLI to install skills from this repository:

```bash
npx skills add ThilinaTLM/agent-skills
```

To install one skill, pass its name:

```bash
npx skills add ThilinaTLM/agent-skills --skill diagram
```

See the [skills.sh CLI docs](https://skills.sh/docs/cli) for agent selection, global installs, updates, and other options.

### Manual install

You can also clone the repo and copy any skill directory into your project's skills location:

```bash
git clone https://github.com/ThilinaTLM/agent-skills.git
cp -r agent-skills/<skill> /path/to/your/skills/
```

Each skill directory contains a `SKILL.md` with full usage instructions.

## License

MIT
