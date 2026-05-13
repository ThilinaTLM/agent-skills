/**
 * Shared runtime helpers used across components.
 *
 * Keep this tiny — it ships in the bundle. New helpers should earn their
 * weight by being used in at least two components.
 */

export const ICONS: Record<string, string> = {
	info: "ⓘ",
	success: "✓",
	warn: "⚠",
	danger: "✕",
	note: "✎",
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
