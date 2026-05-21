# Agent Skills

Reusable AI agent skills — drop a skill directory into your project and your agent gains new capabilities.

## Available Skills

| Skill                  | Description                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| [droid](./droid)       | Android device automation via ADB                                                                |
| [pgtool](./pgtool)     | PostgreSQL database exploration and debugging                                                    |
| [imagegen](./imagegen) | AI image generation via Google Gemini                                                            |
| [diagram](./diagram)   | Render PlantUML, Mermaid, GraphViz, D2, and other diagram sources via Kroki                      |
| [playbook](./playbook) | Create and refine repo-specific `AGENTS.md` files                                                |
| [richdoc](./richdoc)   | Author polished HTML deliverables (reports, design docs, one-pagers) using `rd-*` web components |

## Installation

Clone the repo and copy any skill directory into your project's skills location:

```bash
git clone https://github.com/ThilinaTLM/agent-skills.git
cp -r agent-skills/<skill> /path/to/your/skills/
```

Each skill directory contains a `SKILL.md` with full usage instructions.

## License

MIT
