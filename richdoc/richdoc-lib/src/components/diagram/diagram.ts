/**
 * <rd-diagram lang="…">
 *
 * Server-side diagram rendering via a Kroki-compatible endpoint. One
 * element covers ~25 diagram languages (mermaid, plantuml, graphviz, d2,
 * dbml, bpmn, c4plantuml, erd, …). Source goes out, SVG comes back; no
 * client-side renderer libraries are loaded.
 *
 * URL shape: <endpoint>/<lang>/svg/<deflate-raw + url-safe-base64(source)>
 *
 * Trust contract: every render POSTs/GETs the diagram source to the
 * configured endpoint. The default is kroki.io (the public instance).
 * Override per-element with `endpoint="…"` or set a doc-wide default on
 * `<rd-page diagram-endpoint="…">`.
 *
 * Theme: `theme="<name>"` only meaningful for `lang="plantuml"` and
 * `lang="c4plantuml"`. For dark-mode docs the default is `cyborg-outline`
 * so the diagram doesn't fight the surrounding palette. Set
 * `theme="none"` to disable; an author-written `!theme` line in the
 * source is always respected. Ignored for other langs.
 *
 * Fallback: if `CompressionStream` is unavailable, or the endpoint is
 * unreachable, the element renders the original source inline as a
 * fenced code block.
 */

import { openDiagramViewer } from "../../lib/diagram-viewer.ts";
import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { stripCommonIndent } from "../../lib/text.ts";
import { spec, tagName } from "./diagram.schema.ts";

const MAXIMIZE_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>`;

const DEFAULT_ENDPOINT = "https://kroki.io";
const PLANTUML_DARK_THEME = "cyborg-outline";
const THEMEABLE_LANGS = new Set(["plantuml", "c4plantuml"]);

/** Resolve dark/light mode the same way the rest of richdoc does. */
function isDarkMode(): boolean {
	const explicit = document.documentElement.getAttribute("data-mode");
	if (explicit === "dark") return true;
	if (explicit === "light") return false;
	return !!window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
}

/**
 * Inject a `!theme <name>` directive into PlantUML source. Respects an
 * author-written `!theme` line. Places the directive right after the
 * `@start…` marker so it remains syntactically valid.
 */
function applyPlantumlTheme(source: string, theme: string | null): string {
	if (!theme) return source;
	if (/^\s*!theme\b/m.test(source)) return source;
	const m = source.match(/^[ \t]*@start\w*[^\n]*\n/);
	if (m && m.index !== undefined) {
		const idx = m.index + m[0].length;
		return `${source.slice(0, idx)}!theme ${theme}\n${source.slice(idx)}`;
	}
	return `!theme ${theme}\n${source}`;
}

/**
 * Kroki's standard encoding: zlib-DEFLATE (RFC 1950, *with* headers —
 * NOT raw deflate) then URL-safe base64 (RFC 4648 §5). Works for every
 * Kroki diagram type. Requires `CompressionStream` (Chrome 90+,
 * Firefox 113+, Safari 16.4+); returns null on older engines.
 */
async function encodeForKroki(source: string): Promise<string | null> {
	const CS = (globalThis as { CompressionStream?: typeof CompressionStream }).CompressionStream;
	if (!CS) return null;
	const enc = new TextEncoder().encode(source);
	const stream = new Response(new Blob([enc as BlobPart]).stream().pipeThrough(new CS("deflate")));
	const buf = new Uint8Array(await stream.arrayBuffer());
	// Standard base64 → URL-safe (RFC 4648 §5). Padding is preserved
	// because Kroki accepts both padded and unpadded variants and some
	// reverse proxies strip trailing `=` in URLs.
	let bin = "";
	for (const byte of buf) bin += String.fromCharCode(byte);
	return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_");
}

/**
 * Normalise a Kroki SVG so it scales responsively without distortion.
 * Kroki (and the upstream PlantUML server) often ship SVGs with inline
 * `width`/`height`, `preserveAspectRatio="none"`, and stretch-fill
 * styles that fight our `max-width: 100%`. Strip those so CSS can
 * size the SVG against its viewBox.
 */
function normaliseDiagramSvg(root: SVGElement): void {
	root.removeAttribute("preserveAspectRatio");
	const vb = (root as SVGSVGElement).viewBox?.baseVal;
	if (vb && vb.width > 0 && vb.height > 0) {
		root.setAttribute("width", String(vb.width));
		root.setAttribute("height", String(vb.height));
	} else {
		root.removeAttribute("width");
		root.removeAttribute("height");
	}
	const style = root.getAttribute("style");
	if (style) {
		const cleaned = style
			.split(";")
			.map((s) => s.trim())
			.filter((s) => s && !/^(width|height)\s*:/i.test(s))
			.join("; ");
		if (cleaned) root.setAttribute("style", cleaned);
		else root.removeAttribute("style");
	}
}

/**
 * Resolve the Kroki endpoint to use, in priority order:
 *   1. `endpoint` attribute on this element
 *   2. `diagram-endpoint` attribute on the closest <rd-page>
 *   3. `https://kroki.io`
 */
function resolveEndpoint(host: HTMLElement): string {
	const elAttr = host.getAttribute("endpoint");
	if (elAttr) return elAttr.replace(/\/+$/, "");
	const page = host.closest("rd-page");
	const pageAttr = page?.getAttribute("diagram-endpoint");
	if (pageAttr) return pageAttr.replace(/\/+$/, "");
	return DEFAULT_ENDPOINT;
}

class RdDiagram extends HTMLElement implements Upgradeable {
	_upgraded = false;

	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;

		const lang = (this.getAttribute("lang") || "").toLowerCase();
		const rawSource = stripCommonIndent(this.textContent || "").trim();
		this.textContent = "";

		if (!lang) {
			this._renderFallback(rawSource, "missing required `lang` attribute");
			return;
		}

		const caption = this.getAttribute("caption");
		const title = this.getAttribute("title");

		// Apply plantuml theme injection only for the langs that
		// understand `!theme` directives.
		let source = rawSource;
		if (THEMEABLE_LANGS.has(lang)) {
			const attrTheme = this.getAttribute("theme");
			let theme: string | null;
			if (attrTheme === "none") theme = null;
			else if (attrTheme) theme = attrTheme;
			else theme = isDarkMode() ? PLANTUML_DARK_THEME : null;
			source = applyPlantumlTheme(rawSource, theme);
		}

		const encoded = await encodeForKroki(source);
		if (!encoded) {
			this._renderFallback(rawSource);
			return;
		}

		const endpoint = resolveEndpoint(this);
		const url = `${endpoint}/${lang}/svg/${encoded}`;

		try {
			const res = await fetch(url, { mode: "cors" });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const ct = res.headers.get("content-type") || "";
			if (ct.includes("image/svg")) {
				const svg = await res.text();
				this.innerHTML = svg;
				const root = this.querySelector("svg") as SVGElement | null;
				if (root) {
					normaliseDiagramSvg(root);
					if (title) root.setAttribute("aria-label", title);
				}
				this._installFullscreenButton(title || `${lang} diagram`);
				if (caption) this._appendCaption(caption);
			} else {
				// Non-SVG fallback (some Kroki servers may serve PNG by default).
				const img = el("img", { src: url, alt: title || `${lang} diagram` });
				this.appendChild(img);
				this._installFullscreenButton(title || `${lang} diagram`);
				if (caption) this._appendCaption(caption);
			}
		} catch (err) {
			console.warn(`[richdoc] rd-diagram (${lang}) render failed:`, err);
			this._renderFallback(rawSource);
		}
	}

	_renderFallback(source: string, _reason?: string): void {
		const pre = el("pre", { class: "_rd-diagram-fallback" }, source);
		this.appendChild(pre);
	}

	_appendCaption(text: string): void {
		this.appendChild(el("span", { class: "_rd-diagram-caption" }, text));
	}

	/** Top-right maximize button → shared fullscreen viewer. */
	_installFullscreenButton(label: string): void {
		const target = this.querySelector("svg, img") as SVGElement | HTMLImageElement | null;
		if (!target) return;
		const btn = el("button", {
			type: "button",
			class: "_rd-diagram-fullscreen-btn",
			"aria-label": "View diagram fullscreen",
			html: MAXIMIZE_SVG,
			onClick: (e: Event) => {
				e.preventDefault();
				const clone = target.cloneNode(true) as SVGElement | HTMLImageElement;
				openDiagramViewer({ content: clone, title: label });
			},
		});
		this.appendChild(btn);
	}
}

export function register(): void {
	define(tagName, RdDiagram);
}
export { spec, tagName };
