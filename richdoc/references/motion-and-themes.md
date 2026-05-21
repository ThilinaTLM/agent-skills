# richdoc — themes, motion, prefs, limitations

## Themes

Set on `<rd-page>`:

- `theme="editorial-warm"` (default) — warm cream paper, Fraunces (display) + Geist (body) + Fira Code (mono). Print-magazine voice.
- `theme="graphite-modern"` — modernist palette, Space Grotesk + Inter + JetBrains Mono. Sharper, more technical voice.

Themes carry their own type stacks; switching the theme switches the typography.

## Modes

`mode="light|dark|auto"` on `<rd-page>`. `auto` (default) follows the OS preference. The floating reader prefs picker overrides per origin+path.

## Width

`width="narrow|standard|wide|full"` on `<rd-page>`. Default `standard` (~1280px). Responsiveness is **container-driven** — multi-column layouts, stat cards, and the TOC adapt to the chosen content width, not the viewport.

## Reader prefs

A floating picker auto-appears in the bottom-right corner of every page. It exposes theme, mode, width, and TOC position. Selections persist in `localStorage` per origin+path. Set `prefs="off"` on `<rd-page>` to suppress it.

The `toc` attribute on `<rd-page>` presets the default position (`auto|right|left|top`); the reader pref overrides at runtime.

## Motion vocabulary

Driven by tokens in `richdoc.css`:

- **Page-enter cascade** — the first ~8 direct children of `<rd-page>` fade and lift in on load (~180 ms with a 20 ms stagger).
- **Viewport-entry reveal** — `<rd-stat>`, `<rd-card>`, `<rd-callout>`, `<rd-figure>`, `<rd-event>`, `<rd-step>`, `<rd-update>`, `<rd-progress>`, `<rd-chart>` reveal as they scroll into view.
- **`<rd-stat>` count-up** — numeric values animate from zero on entry. Non-numeric values (`"complete"`, `"42 days"`) render immediately.
- **`<rd-progress>` fill** — the bar interpolates from 0 to its target width on entry.
- **`<rd-detail>`** — chevron (or eye glyph for `variant="reveal"`) and disclosure body height interpolate in browsers that support `interpolate-size`. Applies to every variant.
- **`<rd-tabs>`** — active underline slides between tabs.
- **`<rd-checklist>` / `<rd-step done>`** — check icon scales in when an item is marked done.
- **`<rd-banner>`** — slides in from the top edge on first paint.
- **`<rd-callout type="warn">` / `"danger"`** — one-shot pulse on entry. Other variants stay still.

All motion is gated on `prefers-reduced-motion: reduce` and collapses to instant transitions for users who opt out at the OS level.

## Limitations

- **JS required** for tabs, math, syntax highlighting, charts, sparklines, citation collection, TOC, count-up animation, tabs underline, copy button. CSS-only components: callouts, banners, kvs, cards, sections, cols, detail, hero, badge, references rendering.
- **Internet required on first render** of:
  - `rd-math` — KaTeX from jsDelivr.
  - `rd-code` with a `lang` attribute — highlight.js from jsDelivr.
  - `rd-chart` (including `variant="sparkline"`) — Observable Plot + d3 from jsDelivr.
  - `rd-diagram` — Kroki endpoint (default `https://kroki.io`).
  - `rd-icon` — Lucide from jsDelivr (framework chrome icons are prewarmed).
  Every component degrades gracefully offline: code blocks show raw source, math shows the source, charts render their data as a table, diagrams fall back to a code block of their source, icons show an empty slot of the right size.
- **`rd-diagram` sends source to a third-party server on every render.** The default endpoint is `https://kroki.io` (Kroki's public service). Set `endpoint` on the element or `diagram-endpoint` on `<rd-page>` to a self-hosted Kroki or PlantUML-compatible server for sensitive content. Requires `CompressionStream` (Chrome 90+, Firefox 113+, Safari 16.4+); falls back to a code block on older engines.
- **Multi-file books duplicate the chapter list.** Each chapter file contains the same `<rd-toc>` block. This is intentional — the format must work without a build step and without runtime cross-file fetch.
