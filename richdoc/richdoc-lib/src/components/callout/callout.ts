import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { CALLOUT_ICONS } from "./callout-icons.ts";
import { spec, tagName } from "./callout.schema.ts";

class RdCallout extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const type = this.getAttribute("type") || "info";
		const title = this.getAttribute("title");
		const iconName = CALLOUT_ICONS[type] || CALLOUT_ICONS.info;
		const titleText = title || type.charAt(0).toUpperCase() + type.slice(1);
		const icon = el("span", { class: "_rd-callout-icon", "aria-hidden": "true" });
		const iconTag = document.createElement("rd-icon");
		iconTag.setAttribute("name", iconName);
		iconTag.setAttribute("size", "md");
		icon.appendChild(iconTag);
		this.prepend(
			el(
				"div",
				{ class: "_rd-callout-title" },
				icon,
				el("span", { class: "_rd-callout-text" }, titleText),
			),
		);
		// Warn/danger callouts fire a one-shot pulse on the icon when they
		// enter view. Info/success/note stay neutral — motion is reserved
		// for callouts that genuinely demand attention.
		if (type === "warn" || type === "danger") {
			reveal(this, () => {
				this.classList.add("_rd-pulse");
				window.setTimeout(() => this.classList.remove("_rd-pulse"), 800);
			});
		} else {
			reveal(this);
		}
	}
}

export function register(): void {
	define(tagName, RdCallout);
}
export { spec, tagName };
