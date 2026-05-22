# richdoc-cli tests

Pytest + [syrupy](https://github.com/syrupy-project/syrupy) snapshot
harness for the `richdoc` CLI. The job of this suite is to make every
later refactor safe by snapshotting the **current** CLI behaviour and
failing loudly when it shifts.

## Run

From `richdoc/richdoc-cli/`:

```bash
uv run pytest               # run everything
uv run pytest -k smoke      # smoke subset
uv run pytest --snapshot-update    # update snapshots after an intentional change
```

`uv run pytest` will install the dev extra (pytest, syrupy, lxml-stubs,
…) on first call.

## Layout

```
tests/
  conftest.py            # cli_invoke / cli_invoke_subprocess / fixtures
  fixtures/              # test-only inputs (broken HTML, edge cases)
  helpers/               # per-format normalisers (DOCX semantic summary,
                         # Confluence pretty-XML printer)
  test_smoke.py          # version / help / clean-lint smoke subset
  test_lint.py
  test_export_md.py
  test_export_docx.py    # uses helpers/docx_summary.py for semantic snapshots
  test_publish_confluence.py  # uses helpers/xml_pretty.py + dry-run only
  test_components.py
  test_new_init_update.py
  test_book.py           # unit tests for export/book.py
  test_assets.py         # unit tests for export/common/assets.py
  test_paths.py
  __snapshots__/         # auto-managed by syrupy
```

### Fixture inputs

Most tests reference the canonical reference documents in
`richdoc/examples/` (resolved via the `examples_dir` fixture). The
local `tests/fixtures/` directory is reserved for intentionally-broken
HTML and other inputs that don't belong in the user-facing examples.

Never mutate `examples/` or `tests/fixtures/` from a test — copy to
`tmp_path` via the `copy_to_tmp` fixture first.

## Conventions

- **One snapshot per `(command, fixture)` pair.** Snapshot file naming
  follows syrupy's default (`<test_name>.ambr` per test module).
- **DOCX is snapshotted as a semantic summary**, not raw bytes (see
  `tests/helpers/docx_summary.py`). python-docx is not byte-stable
  across versions; the summary captures paragraphs, headings, tables,
  styles, and image counts.
- **Confluence storage XML is snapshotted pretty-printed** so diffs
  surface real changes, not whitespace noise.
- **Network calls are forbidden** — Kroki rendering is always disabled
  in tests (`--no-render-diagrams`, `--no-render-math`), and Confluence
  publish tests use `--dry-run` only.
- **Update snapshots only with intent.** When a snapshot diff appears,
  read every line of it before running `--snapshot-update`. Use
  `pytest --snapshot-details` to see the full diff inline.

## Snapshot review checklist

When updating a snapshot, the PR description must answer:

- Which behaviour changed?
- Was it intentional (feature, bug fix) or incidental (formatting,
  reordering)?
- For incidental changes: can they be normalised away in the snapshot
  rather than baked into the new fixture?
- For intentional changes: is the change documented in
  `richdoc-cli/CHANGELOG.md` under `Unreleased`?

## Known-Any seams

The CLI uses `dict[str, Any]` for JSON envelopes and `lxml` exposes
`Any`-typed elements throughout. `mypy --strict` has
`disallow_any_explicit = false` and `disallow_any_generics = false`
configured in `pyproject.toml` so these seams don't generate noise.
Tightening them is tracked as a follow-up refactor.
