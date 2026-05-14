import { type Upgradeable, define } from "../../lib/dom.ts";
import { spec, tagName } from "./cols.schema.ts";

class RdCols extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const template = this.getAttribute("template");
		if (template) {
			// Asymmetric layout. Inline style is overridden at the mobile
			// breakpoint by !important in cols.css.
			this.style.setProperty("grid-template-columns", template);
		}
	}
}

export function register(): void {
	define(tagName, RdCols);
}
export { spec, tagName };
