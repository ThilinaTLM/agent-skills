/**
 * Runtime icon resolver. Every `<rd-icon name="…">` resolves through a single
 * lazy path: fetch the matching `lucide-static` SVG from jsDelivr on first
 * reference, cache the inner-SVG markup in memory so repeat uses share one
 * network round-trip, and let the browser HTTP cache (`cache: "force-cache"`)
 * carry that across reloads.
 *
 * Failure mode: if the network request fails (offline, blocked CDN, unknown
 * name) the loader resolves to `null` and `<rd-icon>` renders an empty <svg>
 * shell at the slot's size — the layout never shifts. The host element is
 * marked with `data-rd-icon-missing` so CSS can opt in to a placeholder.
 *
 * Framework chrome (callouts, checklists, banners, …) constructs `<rd-icon>`
 * elements with a small fixed set of names. We prewarm those names at boot
 * (see `prewarmFrameworkIcons`) so the fetches are in flight before any
 * component's `connectedCallback` runs, eliminating a visible icon flash on
 * cold caches without inlining any SVG markup into `richdoc.js`.
 */

import { LUCIDE_CDN_BASE } from "./lucide-version.ts";

const cache = new Map<string, Promise<string | null>>();

/**
 * Strip the outer `<svg …>` wrapper from a Lucide static file and return just
 * the children. Lucide's SVG files are pretty-printed with newlines, so we
 * collapse internal whitespace to keep the inline markup compact when
 * injected into a host <svg> on the page.
 */
function extractInner(raw: string): string | null {
	const m = raw.match(/<svg\b[^>]*>([\s\S]*?)<\/svg>/i);
	if (!m) return null;
	return m[1].replace(/\s+/g, " ").replace(/>\s+</g, "><").trim();
}

export function loadIconInner(name: string): Promise<string | null> {
	const hit = cache.get(name);
	if (hit) return hit;
	const p = fetch(`${LUCIDE_CDN_BASE}/${name}.svg`, { cache: "force-cache" })
		.then((r) => (r.ok ? r.text() : null))
		.then((text) => (text ? extractInner(text) : null))
		.catch(() => null);
	cache.set(name, p);
	return p;
}

/**
 * Icon names hard-coded inside the framework's own components. Prewarming
 * these on script load lets callouts / banners / checklists / details /
 * steps / pros-cons / trees / updates render their chrome icons without a
 * visible flash, because the fetch is in flight before any
 * `connectedCallback` runs.
 *
 * Keep this list in sync with the icon names hard-coded inside
 * `src/components/*` — search for `createElement("rd-icon")` and add any
 * new framework-internal glyph here. Author-supplied icons (e.g.
 * `<rd-node icon="…">`) intentionally do not prewarm.
 */
const FRAMEWORK_ICONS = [
	// callout (CALLOUT_ICONS)
	"info",
	"check",
	"alert-triangle",
	"x-octagon",
	"edit-3",
	// detail
	"eye",
	"chevron-down",
	// banner (BANNER_ICONS)
	"snowflake",
	"archive",
	"eye-off",
	// update (UPDATE_ICONS)
	"package",
	"git-commit",
	"bell",
	// pros-cons / tree
	"x",
	"chevron-right",
] as const;

export function prewarmFrameworkIcons(): void {
	for (const name of FRAMEWORK_ICONS) loadIconInner(name);
}
