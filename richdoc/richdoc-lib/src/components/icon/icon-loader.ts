/**
 * Runtime icon resolver. Synchronous for the inlined core set
 * (`icons-core.ts`); fetches the rest from jsDelivr on first reference
 * and caches the inner-SVG markup in memory so repeat uses share one
 * network round-trip.
 *
 * Failure mode: if the network request fails (offline, blocked CDN,
 * unknown name) the loader resolves to `null` and `<rd-icon>` renders
 * an empty <svg> shell at the slot's size — the layout never shifts.
 */

import { ICONS_CORE } from "./icons-core.ts";
import { LUCIDE_CDN_BASE } from "./lucide-version.ts";

const cache = new Map<string, Promise<string | null>>();

/**
 * Strip the outer `<svg …>` wrapper from a Lucide static file and
 * return just the children. Lucide's SVG files are pretty-printed with
 * newlines, so we collapse internal whitespace to keep the inline
 * markup compact when injected into a host <svg> on the page.
 */
function extractInner(raw: string): string | null {
	const m = raw.match(/<svg\b[^>]*>([\s\S]*?)<\/svg>/i);
	if (!m) return null;
	return m[1].replace(/\s+/g, " ").replace(/>\s+</g, "><").trim();
}

export function loadIconInner(name: string): Promise<string | null> {
	const core = ICONS_CORE[name];
	if (core) return Promise.resolve(core);
	const hit = cache.get(name);
	if (hit) return hit;
	const p = fetch(`${LUCIDE_CDN_BASE}/${name}.svg`, { cache: "force-cache" })
		.then((r) => (r.ok ? r.text() : null))
		.then((text) => (text ? extractInner(text) : null))
		.catch(() => null);
	cache.set(name, p);
	return p;
}

/** True if `name` is in the inlined core set (renders synchronously). */
export function isCoreIcon(name: string): boolean {
	return Object.hasOwn(ICONS_CORE, name);
}
