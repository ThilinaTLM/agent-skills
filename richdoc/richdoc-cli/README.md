# richdoc-cli

Agent-facing CLI for the richdoc skill: scaffold (`new`), install assets (`init`), refresh stale assets (`update`), validate (`lint`), introspect the component vocabulary (`components`), export to markdown / docx (`export`), and publish to Confluence Cloud (`publish confluence`). HTML is the source format and is not an export target.

- See the parent skill: [`../SKILL.md`](../SKILL.md) for the full command reference and component vocabulary.
- Requires `uv` ([install](https://docs.astral.sh/uv/)). First call provisions the Python environment automatically.
- Output is JSON on every command (success and error). Built for AI agents, not humans.

The framework asset build (`richdoc.css` / `richdoc.js` / `schema.json`) lives in `../richdoc-lib/` and is invoked with `pnpm build` from there.

## Source layout

```
src/richdoc_cli/
  cli.py              # click group + JSON-safe error trap
  output.py           # json_ok / json_error envelopes
  schema.py           # rd-* component vocabulary loader
  templates.py        # template discovery
  assets.py           # framework asset filenames (init/new)
  paths.py            # canonical filesystem paths
  mimetypes_ext.py    # mime sniffer used by the export pipeline
  commands/           # one click subcommand per file
    new_.py init_.py update.py lint.py components.py export.py publish.py
  export/             # the export pipeline (md / docx)
    book.py           #   multi-file book discovery
    common/           #   format-agnostic helpers
      assets.py       #     AssetStore (file dedup + remote fetch)
      diagrams.py     #     Kroki POST helper for rd-diagram (any lang)
      walker.py       #     parse_html, inline_text, element_source
      chart_data.py   #     rd-chart data parser (returns ChartTable)
      modes.py        #     ExportMode + plan_outputs (single vs multi)
    md/               #   HTML → GitHub-flavored markdown
      converter.py    #     _Converter state machine + helpers
      handlers_plain.py # plain HTML element handlers
      handlers_rd.py  #   rd-* component handlers
      handler_table.py # the dispatch dict (populates converter.HANDLERS)
      combiner.py     #   single-mode: stitch chapters into one .md
      pipeline.py     #   single + multi orchestration
    docx/             #   HTML → .docx (Word / LibreOffice)
      state.py        #     _State + DocxResult
      document.py     #     Document factory + RichdocCode style
      runs.py         #     _Run, inline runs, hyperlinks, li splitting
      tables.py       #     table cell helpers (borders, shading, fill)
      walker.py       #     render_source / render_children / render_block
      references.py   #     citation collection + References section
      math.py         #     LaTeX → OMML via latex2mathml + MML2OMML.xsl
      handlers_plain.py / handlers_rd.py / handler_table.py
      pipeline.py     #   single + multi orchestration
  publish/            # remote publish targets
    confluence/       #   Confluence Cloud REST publisher
      auth.py         #     flag / env / getpass credential resolution
      client.py       #     stdlib REST client (urllib + email.mime multipart)
      converter.py    #     HTML → storage-format XML state machine
      handlers_plain.py # plain HTML → storage XML
      handlers_rd.py  #     rd-* → storage XML + native macros
      handler_table.py # the dispatch dict
      math.py         #     Kroki TikZ → PNG for rd-math
      pipeline.py     #     create / update pages + upload attachments
```

The `export` package was carved out of two monolithic files (`markdown.py`, `docx_export.py`) so each handler module is small enough to read end-to-end and so the two formats share helpers via `export/common/`. `publish/confluence/` reuses `export/common/` (book discovery, asset store, walker helpers) but emits Confluence storage-format XML instead of one of the export formats.

## Development

Install dev tooling and run the gates locally:

```bash
uv sync --extra dev
uv run ruff check src tests   # lint
uv run mypy src               # type-check
uv run pytest                 # tests + snapshots (see tests/README.md)
```

The snapshot suite under `tests/` makes refactors safe; pair every
behavioural change with a deliberate `pytest --snapshot-update` and
read the diff before committing.

The repo ships a `.pre-commit-config.yaml` at the root that runs ruff,
mypy, and pytest (plus the lib's biome / tsc / vitest) before every
commit. Enable it once per clone:

```bash
pip install pre-commit    # or: uv tool install pre-commit
pre-commit install        # writes .git/hooks/pre-commit
```

Run the full suite manually with `pre-commit run --all-files`. Hooks
are scoped to `^richdoc/` paths so editing other skills in this repo
doesn't trigger them.
