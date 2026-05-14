import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { stripCommonIndent } from "../../lib/text.ts";
import { spec, tagName } from "./plantuml.schema.ts";

const DEFAULT_ENDPOINT = "https://www.plantuml.com/plantuml/svg";
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
				if (root) {
					root.removeAttribute("width");
					root.removeAttribute("height");
				}
			} else {
				// Server returned a non-SVG (PNG fallback path, or error image).
				// Fall through to an <img> so the user at least sees output.
				this.appendChild(el("img", { src: url, alt: "PlantUML diagram" }));
			}
		} catch (err) {
			console.warn("[richdoc] plantuml render failed:", err);
			this.appendChild(el("pre", { class: "_rd-plantuml-fallback" }, rawSource));
		}
	}
}

export function register(): void {
	define(tagName, RdPlantuml);
}
export { spec, tagName };
