# richdoc-cli

Agent-facing CLI for the richdoc skill: scaffold (`new`), install assets (`init`), refresh stale assets (`update`), validate (`lint`), introspect the component vocabulary (`components`), and export to markdown / html / docx (`export`).

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
    new_.py init_.py update.py lint.py components.py export.py
  export/             # the export pipeline (md / html / docx)
    book.py           #   multi-file book discovery
    common/           #   format-agnostic helpers
      assets.py       #     AssetStore (file dedup + remote fetch)
      diagrams.py     #     Kroki POST helper for mermaid / plantuml
      walker.py       #     parse_html, inline_text, element_source
      chart_data.py   #     rd-chart data parser (returns ChartTable)
      modes.py        #     ExportMode + plan_outputs (single vs multi)
    html/             #   HTML → self-contained .bundle.html
      bundler.py      #     inline relative deps into one file
      pipeline.py     #     single + multi orchestration
    md/               #   HTML → GitHub-flavored markdown
      converter.py    #     _Converter state machine + helpers
      handlers_plain.py # plain HTML element handlers
      handlers_rd.py  #   rd-* component handlers
      handler_table.py # the dispatch dict (populates converter.HANDLERS)
      combiner.py     #   single-mode: stitch chapters into one .md
      pipeline.py     #   single + multi orchestration
    docx/             #   HTML → .docx (Confluence-import compatible)
      state.py        #     _State + DocxResult
      document.py     #     Document factory + RichdocCode style
      runs.py         #     _Run, inline runs, hyperlinks, li splitting
      tables.py       #     table cell helpers (borders, shading, fill)
      walker.py       #     render_source / render_children / render_block
      references.py   #     citation collection + References section
      handlers_plain.py / handlers_rd.py / handler_table.py
      pipeline.py     #   single + multi orchestration
```

The `export` package was carved out of two monolithic files (`markdown.py`, `docx_export.py`) so each handler module is small enough to read end-to-end and so the two formats share helpers via `export/common/`.

