import { openDiagramViewer } from "../../lib/diagram-viewer.ts";
import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { stripCommonIndent } from "../../lib/text.ts";
import { spec, tagName } from "./plantuml.schema.ts";

const MAXIMIZE_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>`;

// Default to Kroki rather than the official PlantUML server: it speaks the
// same encoded-URL protocol, returns SVG + permissive CORS, and is the same
// backend `richdoc-cli` uses when pre-rendering diagrams during export, so
// browser-side and CLI-side output stay consistent. Override per-element
// with the `endpoint` attribute (e.g. a self-hosted Kroki or PlantUML
// server for sensitive content).
const DEFAULT_ENDPOINT = "https://kroki.io/plantuml/svg";
/** PlantUML built-in dark theme used when the doc is in dark mode and the
 * author hasn't overridden it. Picked for being line-based and neutral so
 * it integrates with the warm editorial palette without fighting it. */
const DEFAULT_DARK_THEME = "cyborg-outline";

/**
 * Resolve the dark/light mode the same way <rd-mermaid> does: the explicit
 * `data-mode` attribute on <html> wins, then the OS preference.
 */
function isDarkMode(): boolean {
	const explicit = document.documentElement.getAttribute("data-mode");
	if (explicit === "dark") return true;
	if (explicit === "light") return false;
	return !!window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
}

/**
 * Inject a `!theme <name>` directive into PlantUML source. Respects an
 * author-written `!theme` line if one is already present. Places the
 * directive right after `@startuml` (or equivalent `@start…`) so it is
 * syntactically valid in every PlantUML version; falls back to prepending
 * if no start directive is found.
 */
function applyTheme(source: string, theme: string | null): string {
	if (!theme) return source;
	if (/^\s*!theme\b/m.test(source)) return source;
	const m = source.match(/^[ \t]*@start\w*[^\n]*\n/);
	if (m && m.index !== undefined) {
		const idx = m.index + m[0].length;
		return `${source.slice(0, idx)}!theme ${theme}\n${source.slice(idx)}`;
	}
	return `!theme ${theme}\n${source}`;
}

// PlantUML's custom 6-bit alphabet (NOT standard base64).
// Order matters: see https://plantuml.com/text-encoding
const PUML_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_";

function encode6Bit(bytes: Uint8Array): string {
	let out = "";
	for (let i = 0; i < bytes.length; i += 3) {
		const b1 = bytes[i] ?? 0;
		const b2 = bytes[i + 1] ?? 0;
		const b3 = bytes[i + 2] ?? 0;
		const c1 = b1 >> 2;
		const c2 = ((b1 & 0x3) << 4) | (b2 >> 4);
		const c3 = ((b2 & 0xf) << 2) | (b3 >> 6);
		const c4 = b3 & 0x3f;
		out += PUML_ALPHABET[c1 & 0x3f];
		out += PUML_ALPHABET[c2 & 0x3f];
		out += PUML_ALPHABET[c3 & 0x3f];
		out += PUML_ALPHABET[c4 & 0x3f];
	}
	return out;
}

/**
 * Normalise the SVG Kroki/PlantUML returns so it sizes responsively
 * without distorting.
 *
 * Kroki's PlantUML SVG ships with three things that fight our CSS:
 *   1. `preserveAspectRatio="none"` — stretches content to fill the
 *      viewport box instead of preserving viewBox aspect.
 *   2. Inline `style="width:Xpx;height:Ypx;..."` matching the viewBox.
 *      Inline styles beat stylesheet rules, so our
 *      `rd-plantuml svg { height: auto; }` is ignored.
 *   3. Implicit reliance on those for sizing.
 *
 * On narrow containers, `max-width: 100%` clamps the SVG width while
 * the inline `height` stays put — the box ends up at the wrong aspect,
 * and `preserveAspectRatio="none"` then stretches content to fill it.
 * Visible result: a wide diagram crushed horizontally.
 *
 * Fix: drop preserveAspectRatio (default is `xMidYMid meet`, which is
 * what we want), re-derive intrinsic `width`/`height` attributes from
 * the viewBox so CSS has dimensions to scale against, and strip the
 * inline `width`/`height` declarations (keeping other inline styles
 * like the white `background` Kroki sets for light themes).
 */
function normalisePlantumlSvg(root: SVGElement): void {
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
 * Encode a PlantUML source string into the URL-safe token that the
 * PlantUML server (and compatible servers like Kroki) expects.
 *
 * Algorithm: UTF-8 → raw DEFLATE → PlantUML 6-bit alphabet base64.
 * Uses the browser's native CompressionStream (Chrome 90+, FF 113+,
 * Safari 16.4+). Returns null if compression is unsupported.
 */
async function encodePlantUml(source: string): Promise<string | null> {
	const CS = (globalThis as { CompressionStream?: typeof CompressionStream }).CompressionStream;
	if (!CS) return null;
	const enc = new TextEncoder().encode(source);
	const stream = new Response(
		new Blob([enc as BlobPart]).stream().pipeThrough(new CS("deflate-raw")),
	);
	const buf = new Uint8Array(await stream.arrayBuffer());
	return encode6Bit(buf);
}

class RdPlantuml extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const rawSource = stripCommonIndent(this.textContent || "").trim();
		this.textContent = "";

		const attrTheme = this.getAttribute("theme");
		let theme: string | null;
		if (attrTheme === "none") theme = null;
		else if (attrTheme) theme = attrTheme;
		else theme = isDarkMode() ? DEFAULT_DARK_THEME : null;
		const source = applyTheme(rawSource, theme);

		const encoded = await encodePlantUml(source);
		if (!encoded) {
			this.appendChild(el("pre", { class: "_rd-plantuml-fallback" }, rawSource));
			return;
		}

		const endpoint = (this.getAttribute("endpoint") || DEFAULT_ENDPOINT).replace(/\/+$/, "");
		const url = `${endpoint}/${encoded}`;

		try {
			const res = await fetch(url, { mode: "cors" });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const ct = res.headers.get("content-type") || "";
			if (ct.includes("image/svg")) {
				const svg = await res.text();
				this.innerHTML = svg;
				const root = this.querySelector("svg");
				if (root) normalisePlantumlSvg(root);
				this._installFullscreenButton();
			} else {
				// Server returned a non-SVG (PNG fallback path, or error image).
				// Fall through to an <img> so the user at least sees output.
				this.appendChild(el("img", { src: url, alt: "PlantUML diagram" }));
				this._installFullscreenButton();
			}
		} catch (err) {
			console.warn("[richdoc] plantuml render failed:", err);
			this.appendChild(el("pre", { class: "_rd-plantuml-fallback" }, rawSource));
		}
	}

	/** Add a top-right corner button that opens the shared fullscreen
	 * viewer with a clone of the rendered SVG (or img). */
	_installFullscreenButton(): void {
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
				openDiagramViewer({ content: clone, title: "PlantUML diagram" });
			},
		});
		this.appendChild(btn);
	}
}

export function register(): void {
	define(tagName, RdPlantuml);
}
export { spec, tagName };
