import { type Upgradeable, define, el, loadCdnScript, stripCommonIndent } from "../../lib/base.ts";
import { spec, tagName } from "./mermaid.schema.ts";

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
