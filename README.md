# Agent Skills

Reusable AI agent skills — drop a skill directory into your project and your agent gains new capabilities.

## Available Skills

| Skill | Description |
|-------|-------------|
| [droid](./droid) | Android device automation via ADB |
| [pgtool](./pgtool) | PostgreSQL database exploration and debugging |
| [imagegen](./imagegen) | AI image generation via Google Gemini |

## Installation

Clone or download this repo, then copy any skill directory into your project's skills location:

```bash
git clone https://github.com/ThilinaTLM/agent-skills.git
cp -r agent-skills/droid /path/to/your/skills/
```

Or use the skills CLI:

```bash
npx skills add ThilinaTLM/agent-skills/droid
npx skills add ThilinaTLM/agent-skills/pgtool
npx skills add ThilinaTLM/agent-skills/imagegen
```

Each skill directory contains a `SKILL.md` with full usage instructions.

## License

MIT
