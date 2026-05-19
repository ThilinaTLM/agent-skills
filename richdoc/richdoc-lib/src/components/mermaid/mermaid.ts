import { loadCdnScript } from "../../lib/cdn.ts";
import { openDiagramViewer } from "../../lib/diagram-viewer.ts";
import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { stripCommonIndent } from "../../lib/text.ts";
import { spec, tagName } from "./mermaid.schema.ts";

const MAXIMIZE_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>`;

interface MermaidApi {
	initialize: (cfg: Record<string, unknown>) => void;
	render: (id: string, src: string) => Promise<{ svg: string }>;
}

const MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";

let initialised = false;

async function loadMermaid(): Promise<MermaidApi | null> {
	const win = window as typeof window & { mermaid?: MermaidApi };
	const m = await loadCdnScript<MermaidApi>(MERMAID_URL, () => win.mermaid);
	if (!m) return null;
	if (!initialised) {
		const html = document.documentElement;
		const explicit = html.getAttribute("data-mode");
		const isDark =
			explicit === "dark" ||
			(!explicit && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
		m.initialize({
			startOnLoad: false,
			theme: isDark ? "dark" : "default",
			securityLevel: "loose",
		});
		initialised = true;
	}
	return m;
}

class RdMermaid extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const source = stripCommonIndent(this.textContent || "").trim();
		this.textContent = "";
		const mermaid = await loadMermaid();
		if (!mermaid) {
			this.appendChild(el("pre", { class: "_rd-mermaid-fallback" }, source));
			return;
		}
		try {
			const id = `_rd-mmd-${Math.random().toString(36).slice(2, 9)}`;
			const { svg } = await mermaid.render(id, source);
			this.innerHTML = svg;
			this._installFullscreenButton(source);
		} catch (err) {
			console.warn("[richdoc] mermaid render failed:", err);
			this.appendChild(el("pre", { class: "_rd-mermaid-fallback" }, source));
		}
	}

	/** Add a top-right corner button that opens the shared fullscreen
	 * viewer with a clone of the rendered SVG. */
	_installFullscreenButton(_source: string): void {
		const svg = this.querySelector("svg");
		if (!svg) return;
		const btn = el("button", {
			type: "button",
			class: "_rd-diagram-fullscreen-btn",
			"aria-label": "View diagram fullscreen",
			html: MAXIMIZE_SVG,
			onClick: (e: Event) => {
				e.preventDefault();
				const clone = svg.cloneNode(true) as SVGElement;
				openDiagramViewer({ content: clone, title: "Mermaid diagram" });
			},
		});
		this.appendChild(btn);
	}
}

export function register(): void {
	define(tagName, RdMermaid);
}
export { spec, tagName };
