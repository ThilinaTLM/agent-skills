import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { spec, stepSpec, stepTagName, tagName } from "./steps.schema.ts";

class RdSteps extends HTMLElement {
	// Pure CSS — the host element only provides the counter-reset.
}

class RdStep extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const title = this.getAttribute("title") || "";
		const done = this.hasAttribute("done");
		if (done) this.setAttribute("data-done", "");

		// Capture body content before mutating.
		const body = el("div", { class: "_rd-step-body" });
		while (this.firstChild) body.appendChild(this.firstChild);

		// `<rd-step>::before` shows the auto-incremented numeral via CSS
		// counters; we render the title and (optional) done check inside.
		const header = el("div", { class: "_rd-step-header" });
		const titleEl = el("div", { class: "_rd-step-title" }, title);
		header.appendChild(titleEl);
		if (done) {
			const icon = document.createElement("rd-icon");
			icon.setAttribute("name", "check");
			icon.setAttribute("size", "sm");
			icon.setAttribute("aria-label", "Done");
			icon.className = "_rd-step-check";
			header.appendChild(icon);
		}
		this.appendChild(header);
		this.appendChild(body);

		reveal(this);
	}
}

export function register(): void {
	define(tagName, RdSteps);
	define(stepTagName, RdStep);
}

export { spec, tagName, stepSpec, stepTagName };
