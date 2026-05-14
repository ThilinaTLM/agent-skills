/**
 * Pure text helpers — no DOM dependencies.
 */

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
