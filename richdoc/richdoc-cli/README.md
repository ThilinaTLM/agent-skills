# richdoc-cli

Agent-facing CLI for the richdoc skill: scaffold (`new`), install assets (`init`), validate (`lint`), and introspect the component vocabulary (`components`).

- See the parent skill: [`../SKILL.md`](../SKILL.md).
- Requires `uv` ([install](https://docs.astral.sh/uv/)). First call provisions the Python environment automatically.
- Output is JSON on every command (success and error). Built for AI agents, not humans.

The framework asset build (`richdoc.css` / `richdoc.js` / `schema.json`) lives in the parent and is invoked with `bun run build` from `../`.
