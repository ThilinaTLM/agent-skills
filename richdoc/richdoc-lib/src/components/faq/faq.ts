import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { aSpec, aTagName, qSpec, qTagName, spec, tagName } from "./faq.schema.ts";

class RdFaq extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const title = this.getAttribute("title");
		if (title) this.prepend(el("div", { class: "_rd-faq-title" }, title));
	}
}

class RdQ extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const question = this.getAttribute("question") || "";
		const open = this.hasAttribute("open");

		// Pull the <rd-a> children into the details body. Anything that
		// isn't a recognised child still gets moved in, defensively.
		const details = el("details", open ? { open: true } : {});
		const chevron = document.createElement("rd-icon");
		chevron.setAttribute("name", "chevron-down");
		chevron.setAttribute("size", "sm");
		chevron.setAttribute("aria-hidden", "true");
		chevron.className = "_rd-faq-chevron";

		const summary = el(
			"summary",
			{ class: "_rd-faq-summary" },
			el("span", { class: "_rd-faq-question" }, question),
			chevron,
		);
		details.appendChild(summary);

		while (this.firstChild) details.appendChild(this.firstChild);
		this.appendChild(details);
	}
}

class RdA extends HTMLElement {
	// Pure container; CSS styles the inner content.
}

export function register(): void {
	define(tagName, RdFaq);
	define(qTagName, RdQ);
	define(aTagName, RdA);
}

export { spec, tagName, qSpec, qTagName, aSpec, aTagName };
