# tests/fixtures

Test-only inputs that don't belong in the user-facing `richdoc/examples/`
directory:

- `broken/` — HTML files with intentional schema violations, used to
  exercise specific lint rules. One file per rule, named after the rule.
- `book-drift/` — copies of `richdoc/examples/book/` with the TOC of
  one chapter deliberately mutated, to exercise `book-toc-drift`.
- `hero-nav-fixable/` — single-chapter excerpts with redundant `<a>`
  children in `<rd-hero>`, used to verify `richdoc lint --fix` is
  idempotent.

When adding a new fixture, also add the test that exercises it (don't
ship unreferenced fixtures). When removing a test, remove the fixture
too.
