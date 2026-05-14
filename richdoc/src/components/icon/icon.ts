import { define, type Upgradeable } from "../../lib/base.ts";
import { ICONS } from "../../lib/icons.ts";
import { spec, tagName } from "./icon.schema.ts";

const SVG_NS = "http://www.w3.org/2000/svg";

class RdIcon extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const name = this.getAttribute("name") || "";
		const label = this.getAttribute("label");
		const inner = ICONS[name];
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
		if (inner) {
			// Vendored Lucide paths are trusted markup.
			svg.insertAdjacentHTML("beforeend", inner);
		}
		this.innerHTML = "";
		this.appendChild(svg);
	}
}

export function register(): void {
	define(tagName, RdIcon);
}
export { spec, tagName };
