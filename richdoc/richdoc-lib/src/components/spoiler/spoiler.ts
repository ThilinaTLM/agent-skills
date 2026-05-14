import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./spoiler.schema.ts";

/**
 * <rd-spoiler> — content hidden behind a "reveal" button. Useful for
 * runbook solutions, exam answers, opinionated takes. Toggles the
 * `data-revealed` attribute on click.
 */
class RdSpoiler extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const label = this.getAttribute("label") || "Reveal";

		// Move existing content into a body wrapper so we can hide/show it.
		const body = el("div", { class: "_rd-spoiler-body" });
		while (this.firstChild) body.appendChild(this.firstChild);

		const icon = document.createElement("rd-icon");
		icon.setAttribute("name", "eye");
		icon.setAttribute("size", "sm");
		icon.setAttribute("aria-hidden", "true");

		const labelText = el("span", { class: "_rd-spoiler-label-text" }, label);
		const button = el(
			"button",
			{
				type: "button",
				class: "_rd-spoiler-button",
				"aria-expanded": "false",
			},
			icon,
			labelText,
		);
		button.addEventListener("click", () => {
			const open = this.hasAttribute("data-revealed");
			if (open) {
				this.removeAttribute("data-revealed");
				button.setAttribute("aria-expanded", "false");
				labelText.textContent = label;
			} else {
				this.setAttribute("data-revealed", "");
				button.setAttribute("aria-expanded", "true");
				labelText.textContent = "Hide";
			}
		});

		this.appendChild(button);
		this.appendChild(body);
	}
}

export function register(): void {
	define(tagName, RdSpoiler);
}
export { spec, tagName };
