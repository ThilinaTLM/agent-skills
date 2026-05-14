import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./detail.schema.ts";

class RdDetail extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const summary = this.getAttribute("summary") || "Details";
		const open = this.hasAttribute("open");
		const details = el("details", open ? { open: true } : {});

		// Summary structure: label on the left, chevron-down on the right.
		// The chevron is a real <rd-icon> so its stroke weight, size, and
		// theming match every other glyph in the framework. CSS rotates it
		// 180° when [open].
		const chevron = document.createElement("rd-icon");
		chevron.setAttribute("name", "chevron-down");
		chevron.setAttribute("size", "sm");
		chevron.setAttribute("aria-hidden", "true");
		chevron.className = "_rd-detail-chevron";

		const summaryEl = el(
			"summary",
			{ class: "_rd-detail-summary" },
			el("span", { class: "_rd-detail-text" }, summary),
			chevron,
		);
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
