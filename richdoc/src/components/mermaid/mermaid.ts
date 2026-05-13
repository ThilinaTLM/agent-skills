import { type Upgradeable, define, el, stripCommonIndent } from "../../lib/base.ts";
import { spec, tagName } from "./mermaid.schema.ts";

interface MermaidApi {
	initialize: (cfg: Record<string, unknown>) => void;
	render: (id: string, src: string) => Promise<{ svg: string }>;
}

let loader: Promise<MermaidApi | null> | null = null;

function loadMermaid(): Promise<MermaidApi | null> {
	if (loader) return loader;
	loader = new Promise((resolve) => {
		const win = window as typeof window & { mermaid?: MermaidApi };
		if (win.mermaid) {
			resolve(win.mermaid);
			return;
		}
		const script = document.createElement("script");
		script.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
		script.async = true;
		script.onload = () => {
			const m = win.mermaid;
			if (!m) {
				resolve(null);
				return;
			}
			const isDark =
				document.documentElement.getAttribute("data-theme") === "dark" ||
				(!document.documentElement.hasAttribute("data-theme") &&
					window.matchMedia &&
					window.matchMedia("(prefers-color-scheme: dark)").matches);
			m.initialize({
				startOnLoad: false,
				theme: isDark ? "dark" : "default",
				securityLevel: "loose",
			});
			resolve(m);
		};
		script.onerror = (err) => {
			console.warn("[richdoc] mermaid CDN load failed:", err);
			resolve(null);
		};
		document.head.appendChild(script);
	});
	return loader;
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
		} catch (err) {
			console.warn("[richdoc] mermaid render failed:", err);
			this.appendChild(el("pre", { class: "_rd-mermaid-fallback" }, source));
		}
	}
}

export function register(): void {
	define(tagName, RdMermaid);
}
export { spec, tagName };
