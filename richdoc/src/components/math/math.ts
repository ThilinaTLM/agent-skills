import {
	type Upgradeable,
	define,
	el,
	loadCdnScript,
	loadCdnStyle,
	stripCommonIndent,
} from "../../lib/base.ts";
import { spec, tagName } from "./math.schema.ts";

interface KatexApi {
	render: (
		expression: string,
		element: HTMLElement,
		options: { displayMode?: boolean; throwOnError?: boolean; output?: string },
	) => void;
}

const KATEX_JS = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js";
const KATEX_CSS = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css";

function loadKatex(): Promise<KatexApi | null> {
	const win = window as typeof window & { katex?: KatexApi };
	loadCdnStyle(KATEX_CSS);
	return loadCdnScript<KatexApi>(KATEX_JS, () => win.katex);
}

class RdMath extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const source = stripCommonIndent(this.textContent || "").trim();
		const display = this.getAttribute("display") || "block";
		this.textContent = "";
		const katex = await loadKatex();
		if (!katex) {
			this.appendChild(el("pre", { class: "_rd-math-fallback" }, source));
			return;
		}
		try {
			katex.render(source, this, {
				displayMode: display !== "inline",
				throwOnError: false,
				output: "html",
			});
		} catch (err) {
			console.warn("[richdoc] math render failed:", err);
			this.appendChild(el("pre", { class: "_rd-math-fallback" }, source));
		}
	}
}

export function register(): void {
	define(tagName, RdMath);
}
export { spec, tagName };
