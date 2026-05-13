import { type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tagName } from "./detail.schema.ts";

class RdDetail extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const summary = this.getAttribute("summary") || "Details";
		const open = this.hasAttribute("open");
		const details = el("details", open ? { open: true } : {});
		const summaryEl = el("summary", { class: "_rd-detail-summary" }, summary);
		details.appendChild(summaryEl);
		// Move existing children into the details wrapper.
		while (this.firstChild) details.appendChild(this.firstChild);
		this.appendChild(details);
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdDetail);
}
export { spec, tagName };
