import { type Upgradeable, define } from "../../lib/base.ts";
import { isCoreIcon, loadIconInner } from "../../lib/icon-loader.ts";
import { spec, tagName } from "./icon.schema.ts";

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * Create the outer <svg> shell with the editorial stroke settings.
 * Empty by default — `connectedCallback` either fills it synchronously
 * (core icon) or asynchronously after the CDN fetch resolves.
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

		if (isCoreIcon(name)) {
			// Synchronous path: no layout shift, no async flash.
			const inner = await loadIconInner(name);
			if (inner) svg.insertAdjacentHTML("beforeend", inner);
			return;
		}

		// Lazy CDN path. Re-check `_upgraded`/parent after await so a
		// disconnected element doesn't end up with mismatched markup.
		const inner = await loadIconInner(name);
		if (!inner) {
			this.setAttribute("data-rd-icon-missing", "");
			return;
		}
		// Only mutate if we're still hosting the original shell.
		if (this.firstChild === svg) {
			svg.insertAdjacentHTML("beforeend", inner);
		}
	}
}

export function register(): void {
	define(tagName, RdIcon);
}
export { spec, tagName };
