# Authoring guide — adding or changing a richdoc component

This file is the contract between the framework and anyone (human or agent) who wants to extend it. If you find yourself doing something not covered here, fix this file first.

## When to add a component

The bar is high on purpose. Every new tag is something the agent must remember and the reader must learn to recognize. Before adding one, check:

1. **Is there a clear, recurring use case?** "I want to render X" needs at least two or three plausible documents that would use it.
2. **Does the existing vocabulary fail?** Could you achieve a reasonable result with `<rd-card>`, `<rd-callout>`, `<rd-kv>`, `<rd-cols>`, `<rd-compare>`, or `<rd-stat>`?
3. **Is the visual idea simple?** Components are layout primitives, not full apps. A complex interactive widget belongs in a separate library, not in richdoc.
4. **Does it fit in ~30 lines of CSS and ~30 lines of TS?** If not, the design is probably too ambitious.

If a component fails these checks, do not add it. Open an issue / discussion instead.

## Anatomy of a component

Each component lives in `src/components/<name>/` and has exactly three files. We'll use `card` as the canonical example.

```
src/components/card/
├── card.schema.ts      # vocabulary spec — read by the linter
├── card.ts             # custom element class + register()
└── card.css            # styles, scoped under the tag selector
```

### `card.schema.ts` — vocabulary spec

Pure data. No runtime, no DOM. The schema is what the linter and the `richdoc components` command see.

```ts
import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-card";
export const spec: TagSpec = {
  optional: ["title", "accent"],
  customChildren: "any",
  enums: {
    accent: ["info", "success", "warn", "danger", "muted"],
  },
};
```

`TagSpec` fields:

| Field | Meaning |
| --- | --- |
| `required` | Attributes that must be present and non-empty. |
| `optional` | Attributes that are recognized but optional. |
| `customChildren` | Allowed `rd-*` children: an array of tag names, or the literal `"any"`. Plain HTML children are always permitted. Omit the field if the tag is a leaf. |
| `allowedParents` | If set, this tag is only valid as a direct child of these tags. Used for `rd-tab` (inside `rd-tabs`), `rd-cell` (inside `rd-row-cells`), etc. |
| `enums` | Per-attribute allowed values. Mismatch is a lint error. |

If a single component module contributes multiple tags (e.g. `kv.ts` ships both `rd-kv` and `rd-row`), export `tagName` + `spec` plus secondary `<thing>TagName` + `<thing>Spec` constants.

### `card.ts` — custom element

The class implements the behavior and `register()` defines it. Imports from `lib/base.ts` should be the only runtime dependency.

```ts
import { define, el, type Upgradeable } from "../../lib/base.ts";
import { spec, tagName } from "./card.schema.ts";

class RdCard extends HTMLElement implements Upgradeable {
  _upgraded = false;
  connectedCallback() {
    if (this._upgraded) return;
    const title = this.getAttribute("title");
    if (title) this.prepend(el("div", { class: "_rd-card-header" }, title));
    this._upgraded = true;
  }
}

export function register(): void {
  define(tagName, RdCard);
}
export { spec, tagName };
```

Rules:

- **Idempotent upgrade.** Always guard `connectedCallback` with `_upgraded`. The DOM may move elements around; the upgrade must not run twice.
- **Use `define()` from `lib/base.ts`.** It no-ops if the element is already defined. Hot reload friendly.
- **Use `el()` for any generated chrome.** It's a tiny helper that maps `{ class, html, onclick }` and children. Avoid manual `document.createElement` + property assignment unless you have a specific reason.
- **Prefix internal classes with `_rd-`.** This guarantees they never collide with user content or future plain-CSS hooks.
- **Re-export `spec` and `tagName` from the schema** so the build's registry can import everything in one place.

If a component contributes multiple custom elements (e.g. `rd-tabs` + `rd-tab`), define both classes in the same file and register both inside `register()`.

### `card.css` — styles

Everything must be scoped under the tag selector. No global classes. No `*` selectors. Internal classes start with `_rd-`. **Read tokens from `src/styles/tokens.css` only** — no literal colors, no literal `font-size`/`font-weight`/`line-height`/`letter-spacing`, no literal spacing or radius numbers. Em-relative values (`0.7em`, `1.6em`) are fine where the size must scale with surrounding text (icons, ornaments). Every other size must come from a `--rd-*` token. This is what makes themes work.

```css
rd-card {
  display: block;
  background: var(--rd-bg-elev);
  border: 1px solid var(--rd-border);
  border-radius: var(--rd-radius);
  padding: var(--rd-space-4) var(--rd-space-5);
  margin: 0 0 var(--rd-space-4);
}
rd-cols > rd-card {
  margin: 0;
  height: 100%;
}
rd-card > ._rd-card-header {
  font-weight: 600;
  border-bottom: 1px solid var(--rd-border);
  padding-bottom: var(--rd-space-2);
}
```

If the component needs to behave differently inside a known parent (e.g. `rd-cols > rd-card`), the rule lives here, not in the parent's CSS. Each component's styles are self-contained.

## Wiring a new component in

Three edits, all small.

1. **`src/styles/index.css`** — add an `@import` in the right cascade slot (under the component-block comment):

   ```css
   @import "../components/<name>/<name>.css";
   ```

2. **`src/schema-registry.ts`** — add a schema import and a registry entry. The order in `SCHEMA_ENTRIES` determines the order in `assets/schema.json`, `richdoc components --plain`, and the SKILL.md table — pick a position that fits the existing grouping (Structure, Information blocks, Comparison & code, Sequenced & interactive).

3. **`src/registry.ts`** — add the implementation import and append `<name>.register` to `REGISTRATIONS`.

That's it. Run `bun run build` (or `richdoc build`). The build:

- Recompiles `assets/richdoc.js` and `assets/richdoc.css`.
- Regenerates `assets/schema.json` from the schema-registry.
- Rewrites `assets/version.txt` with the new bundle hash.
- Validates `examples/showcase.html` against the new schema and fails if it regressed.

## Adding a theme

Themes are pure data. Adding one does not require any JS or component changes.

1. Append two blocks to `src/styles/tokens.css` under the existing `editorial-warm` blocks:

   ```css
   /* my-theme — LIGHT */
   :root[data-theme="my-theme"],
   :root[data-theme="my-theme"][data-mode="light"] {
     --rd-bg: …;
     /* full color + shadow palette — mirror the structure of editorial-warm */
   }

   /* my-theme — DARK */
   :root[data-theme="my-theme"][data-mode="dark"] {
     /* full dark palette */
   }
   ```

   You must provide **every** color token (`--rd-bg`, `--rd-fg`, all status colors with `*-fg` and `*-soft` variants, etc.). Missing tokens fall through to the default `:root` block (editorial-warm light), producing visual inconsistency.

2. Add the theme name to the `theme` enum in `src/components/page/page.schema.ts`:

   ```ts
   enums: {
     theme: ["editorial-warm", "my-theme"],
     mode:  ["light", "dark", "auto"],
   },
   ```

3. Run `bun run build`. Authors can now opt in with `<rd-page theme="my-theme">` or `<html data-theme="my-theme">`.

Typography tokens (font stacks, sizes, weights, leadings, trackings) and structural tokens (spacing, radius, layout widths) are theme-agnostic. If you want a theme with different fonts, override `--rd-font-display` and `--rd-font-body` inside the theme's block alongside the colors. Update the top-of-file Google Fonts `@import` if the new family isn't loaded yet.

## Updating an existing component

The same three files own the surface. Tightening the schema may break existing docs — run `richdoc lint` against any docs you care about before publishing.

Backwards-compatible changes (safe):
- Adding an optional attribute.
- Adding a new value to an `enums` set.
- Adding allowed children to `customChildren`.

Breaking changes (require a vocabulary bump):
- Removing or renaming an attribute.
- Tightening `required` (adding a new required attribute).
- Removing values from `enums`.
- Removing allowed children.

There is no formal semver on the asset bundle yet, but `assets/version.txt` records the bundle hash so consumers can detect a change.

## Testing

`bun run build` is the smoke test. It rebuilds the bundle, regenerates the schema, and lints the showcase against the result. Any of those failing fails the build.

Before sending the change, also:

```bash
# Open the showcase via file:// — make sure no console errors.
agent-browser --allow-file-access open "file://$(pwd)/examples/showcase.html"
agent-browser eval 'customElements.get("rd-<name>") ? "ok" : "fail"'
```

If the new component changes the showcase visually, screenshot the relevant section and include it in the change description.

## What lives where (reference)

| Concern | File |
| --- | --- |
| Vocabulary order, SKILL.md table order | `src/schema-registry.ts` |
| JS registration order | `src/registry.ts` |
| CSS cascade order | `src/styles/index.css` |
| Shared runtime helpers | `src/lib/base.ts` |
| Type definitions | `src/lib/types.ts` |
| Build pipeline | `build.ts` |
| Generated artifacts (do not hand-edit) | `assets/` |
| CLI linter — reads schema | `richdoc-cli/src/commands/lint.ts` |
| CLI introspection | `richdoc-cli/src/commands/components.ts` |

If you find yourself wanting to edit a file in `assets/`, stop — your change belongs in `src/` and will be regenerated by the next build.
