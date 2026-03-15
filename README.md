<div align="center">

<img src="assets/banner.png" alt="Agent Skills" width="600" />

[Claude Code](https://claude.ai/code) • [Cursor](https://cursor.sh) • [GitHub Copilot](https://github.com/features/copilot) • and more

</div>

---

## Installation

### Claude Code

```bash
/plugin marketplace add ThilinaTLM/agent-skills
/plugin install specdev@tlmtech
/plugin install pgtool@tlmtech
/plugin install droid@tlmtech
/plugin install webnav@tlmtech
/plugin install imagegen@tlmtech
/plugin install codex@tlmtech
```

### Other Tools (Cursor, Copilot, etc.)

```bash
npx skills add ThilinaTLM/agent-skills
```

Or install individual skills:

```bash
npx skills add ThilinaTLM/agent-skills/specdev
npx skills add ThilinaTLM/agent-skills/pgtool
npx skills add ThilinaTLM/agent-skills/droid
npx skills add ThilinaTLM/agent-skills/webnav
npx skills add ThilinaTLM/agent-skills/imagegen
npx skills add ThilinaTLM/agent-skills/codex
```

---

## Available Skills

| Skill                  | Description                                       | Tags                      |
| ---------------------- | ------------------------------------------------- | ------------------------- |
| [specdev](./specdev)   | Spec-driven development for multi-session tasks   | `productivity` `workflow` |
| [pgtool](./pgtool)     | PostgreSQL database exploration and debugging     | `database` `sql`          |
| [droid](./droid)       | Android device automation via ADB                 | `testing` `android`       |
| [webnav](./webnav)     | Browser automation via Chrome extension           | `browser` `automation`    |
| [imagegen](./imagegen) | AI image generation via Google Gemini             | `images` `generative-ai`  |
| [codex](./codex)       | OpenAI Codex CLI for research and second opinions | `openai` `research`       |

---

## Contributing

Each skill is self-contained in its own directory:

```
skill-name/
├── .claude-plugin/plugin.json
└── skills/skill-name/
    ├── SKILL.md          # Main skill definition
    └── scripts/          # CLI tools (if any)
```

## License

MIT
