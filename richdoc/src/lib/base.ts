/**
 * Shared runtime helpers used across components.
 *
 * Keep this tiny — it ships in the bundle. New helpers should earn their
 * weight by being used in at least two components.
 */

/**
 * Mapping from callout type to a Lucide icon name (vendored in icons.ts).
 * Callout renders <rd-icon name="…"> rather than a Unicode glyph so the
 * marker has consistent stroke weight and inherits text color.
 */
export const CALLOUT_ICONS: Record<string, string> = {
	info: "info",
	success: "check",
	warn: "alert-triangle",
	danger: "x-octagon",
	note: "edit-3",
};

type ElProps = Record<string, string | number | boolean | null | undefined | ((ev: Event) => void)>;
type ElChild = Node | string | null | undefined;

/** Lightweight DOM builder. Mirrors React.createElement ergonomics. */
export function el(tag: string, props: ElProps = {}, ...children: ElChild[]): HTMLElement {
	const node = document.createElement(tag);
	for (const [k, v] of Object.entries(props)) {
		if (v === undefined || v === null || v === false) continue;
		if (k === "class") node.className = String(v);
		else if (k === "html") node.innerHTML = String(v);
		else if (k.startsWith("on") && typeof v === "function") {
			node.addEventListener(k.slice(2).toLowerCase(), v as EventListener);
		} else {
			node.setAttribute(k, v === true ? "" : String(v));
		}
	}
	for (const c of children) {
		if (c == null) continue;
		node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
	}
	return node;
}

/** Register a custom element only once. */
export function define(name: string, ctor: CustomElementConstructor): void {
	if (!customElements.get(name)) customElements.define(name, ctor);
}

/** URL-safe slug for headings, used for anchor ids. */
export function slugify(s: string): string {
	return String(s)
		.toLowerCase()
		.trim()
		.replace(/[^\w\s-]/g, "")
		.replace(/\s+/g, "-")
		.replace(/-+/g, "-")
		.slice(0, 60);
}

/**
 * Strip common leading whitespace from a multi-line string.
 * Used by <rd-code> and <rd-mermaid> so authors can indent their content
 * to match surrounding HTML without it leaking into the rendered output.
 */
export function stripCommonIndent(s: string): string {
	const lines = s.replace(/^\n+/, "").replace(/\s+$/, "").split("\n");
	let min = Number.POSITIVE_INFINITY;
	for (const line of lines) {
		if (line.trim().length === 0) continue;
		const m = line.match(/^[ \t]*/);
		if (m) min = Math.min(min, m[0].length);
	}
	if (!Number.isFinite(min) || min === 0) return lines.join("\n");
	return lines.map((l) => l.slice(min)).join("\n");
}

/** Idempotency flag used by every component to guard against double-upgrade. */
export interface Upgradeable extends HTMLElement {
	_upgraded?: boolean;
}

/**
 * Shared CDN script loader. Resolves to the global your code exposes
 * (e.g. window.mermaid, window.katex, window.hljs) or null on failure.
 * Idempotent: parallel calls for the same URL share a single promise.
 */
const cdnLoaders = new Map<string, Promise<unknown>>();
export function loadCdnScript<T = unknown>(
	url: string,
	getGlobal: () => T | undefined,
): Promise<T | null> {
	const existing = cdnLoaders.get(url) as Promise<T | null> | undefined;
	if (existing) return existing;
	const p = new Promise<T | null>((resolve) => {
		const already = getGlobal();
		if (already) return resolve(already);
		const s = document.createElement("script");
		s.src = url;
		s.async = true;
		s.onload = () => resolve(getGlobal() ?? null);
		s.onerror = () => {
			console.warn(`[richdoc] CDN script load failed: ${url}`);
			resolve(null);
		};
		document.head.appendChild(s);
	});
	cdnLoaders.set(url, p);
	return p;
}

/** Inject a stylesheet from a CDN once. Tagged to avoid duplicates. */
export function loadCdnStyle(url: string): void {
	if (document.querySelector(`link[data-rd-cdn="${url}"]`)) return;
	const l = document.createElement("link");
	l.rel = "stylesheet";
	l.href = url;
	l.setAttribute("data-rd-cdn", url);
	document.head.appendChild(l);
}

/**
 * Parse a "line-range" attribute like "3,5-7,11" into a set of 1-based
 * line numbers. Used by <rd-code highlight="…"> and friends.
 */
export function parseLineRanges(spec: string | null | undefined): Set<number> {
	const out = new Set<number>();
	if (!spec) return out;
	for (const part of spec.split(",")) {
		const t = part.trim();
		if (!t) continue;
		const m = t.match(/^(\d+)(?:-(\d+))?$/);
		if (!m) continue;
		const a = Number(m[1]);
		const b = m[2] ? Number(m[2]) : a;
		for (let i = Math.min(a, b); i <= Math.max(a, b); i++) out.add(i);
	}
	return out;
}

/** Escape HTML special characters for safe innerHTML interpolation. */
export function escapeHtml(s: string): string {
	return s
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}
