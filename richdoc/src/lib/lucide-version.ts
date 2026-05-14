/**
 * Single source of truth for the Lucide release richdoc is built against.
 *
 * The version is read in two places:
 *
 *   1. At richdoc build time, `build.ts` walks `node_modules/lucide-static`
 *      to enumerate every available icon name and bakes the list into the
 *      schema (so `richdoc lint` validates `<rd-icon name="…">` strictly).
 *
 *   2. At runtime, `icon-loader.ts` fetches non-core icons from jsDelivr
 *      using `LUCIDE_CDN_BASE` so the doc only carries ~30 inlined icons
 *      yet can reference any of ~1900 Lucide glyphs.
 *
 * Bumping the pin is a one-line change here followed by `bun install` and
 * `bun run build`. Keep the version aligned with the `lucide-static`
 * devDependency in `package.json`.
 */

export const LUCIDE_VERSION = "1.16.0";

export const LUCIDE_CDN_BASE = `https://cdn.jsdelivr.net/npm/lucide-static@${LUCIDE_VERSION}/icons`;
