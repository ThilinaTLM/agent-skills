# diagram-cli

Python implementation of the `diagram` skill. Thin client over the
[Kroki](https://kroki.io) HTTP API.

## Layout

```
diagram-cli/
├── diagram[.cmd|.ps1]      # launchers — run uv to invoke the CLI
├── pyproject.toml          # name=diagram-cli, console-script `diagram`
└── src/diagram_cli/
    ├── catalog.py          # supported diagram types, formats, extensions
    ├── inputs.py           # source + type resolution
    ├── endpoint.py         # Kroki endpoint resolution
    ├── render.py           # HTTP call to Kroki
    ├── output.py           # JSON envelope writer
    ├── cli.py              # click group + entrypoint
    └── commands/
        ├── render.py       # `diagram render`
        └── types.py        # `diagram types`
```

## Run locally

```bash
./diagram render --source 'digraph G { Hello -> World }' --type graphviz --format svg --output /tmp/hello.svg
./diagram types
./diagram types mermaid
```

`uv` provisions the venv on first call.

## Updating the type/format table

Kroki occasionally adds output formats. Edit `src/diagram_cli/catalog.py` —
that file is the single source of truth used both for pre-flight format
validation and for the `diagram types` output.
