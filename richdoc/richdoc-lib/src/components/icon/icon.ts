import { type Upgradeable, define } from "../../lib/dom.ts";
import { loadIconInner, prewarmFrameworkIcons } from "./icon-loader.ts";
import { spec, tagName } from "./icon.schema.ts";

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * Create the outer <svg> shell with the editorial stroke settings. The shell
 * is appended synchronously so the element occupies its final size on first
 * paint; `connectedCallback` fills in the inner geometry once the CDN fetch
 * resolves (or marks the element missing on failure).
 */
function makeShell(label: string | null): SVGSVGElement {
	const svg = document.createElementNS(SVG_NS, "svg");
	svg.setAttribute("viewBox", "0 0 24 24");
	svg.setAttribute("fill", "none");
	svg.setAttribute("stroke", "currentColor");
	svg.setAttribute("stroke-width", "1.75");
	svg.setAttribute("stroke-linecap", "round");
	svg.setAttribute("stroke-linejoin", "round");
	if (label) {
		svg.setAttribute("role", "img");
		svg.setAttribute("aria-label", label);
		const titleEl = document.createElementNS(SVG_NS, "title");
		titleEl.textContent = label;
		svg.appendChild(titleEl);
	} else {
		svg.setAttribute("aria-hidden", "true");
		svg.setAttribute("focusable", "false");
	}
	return svg;
}

class RdIcon extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const name = this.getAttribute("name") || "";
		const label = this.getAttribute("label");
		const svg = makeShell(label);
		this.innerHTML = "";
		this.appendChild(svg);
		if (!name) return;

		const inner = await loadIconInner(name);
		if (!inner) {
			this.setAttribute("data-rd-icon-missing", "");
			return;
		}
		// Guard: only mutate if we're still hosting the original shell — the
		// element may have been replaced or re-rendered while awaiting.
		if (this.firstChild === svg) {
			svg.insertAdjacentHTML("beforeend", inner);
		}
	}
}

export function register(): void {
	define(tagName, RdIcon);
	// Fire framework-internal icon fetches the moment richdoc.js boots, so the
	// CDN round-trips overlap with the rest of the document parse and almost
	// always resolve before the consuming component upgrades.
	prewarmFrameworkIcons();
}
export { spec, tagName };
