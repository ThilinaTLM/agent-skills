# Changelog

## 0.5.1

### Fixed

- **`rd-progress` rendered as `8000%` in markdown.** Bare numeric values
  (`<rd-progress value="80">`) were unconditionally multiplied by 100.
  Parser now matches the JS behavior: values > 1 are treated as already
  being percentages, values ≤ 1 as fractions. Shared helper at
  `export/common/progress.py` keeps md and docx in sync.

- **`rd-progress` showed a bare numeric value in DOCX** (`Coverage: 80`).
  Now renders as `Coverage: 80%` using the same shared parser.

- **`rd-steps` body text was dropped in DOCX.** The previous walker only
  visited element children, so text nodes around inline tags (e.g. the
  `"Run "` and `"."` around `<code>richdoc new</code>`) disappeared and
  steps with no inline elements rendered with empty bodies. Step bodies
  now split into inline runs (joined to the list-item paragraph with an
  em-dash separator) and block children (rendered as follow-on
  paragraphs).

- **`rd-callout` body paragraphs were duplicated in DOCX.** The handler
  emitted `_inline_runs` of the entire element *and* re-emitted each
  block child. Callouts with block children now skip the inline pass;
  inline-only callouts still get a single combined run.

- **`rd-pros-cons` produced an awkward zipped table in DOCX** where
  unrelated pros and cons shared rows and asymmetric lists left empty
  cells. Pros and cons now render as two stacked sections (heading +
  bulleted list each), matching the `rd-cols` linearisation convention.

- **`richdoc export md -o -` created a literal file named `-`** instead
  of writing to stdout. The `cmd_md` Click handler now mirrors `cmd_html`
  / `cmd_docx`: `-o -` writes the markdown to stdout in single mode,
  errors out in multi mode, and skips asset materialisation. New
  `export.md.pipeline.render_to_string` helper backs the stdout path.

### Internal

- New `export/common/progress.py` shared between md and docx exporters.
- New `export/md/pipeline.render_to_string()` for filesystem-free
  markdown generation.

## 0.5.0

Initial tagged release covered by this changelog.
