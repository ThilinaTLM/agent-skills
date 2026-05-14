import { CALLOUT_ICONS, type Upgradeable, define, el } from "../../lib/base.ts";
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
	}
}

export function register(): void {
	define(tagName, RdCallout);
}
export { spec, tagName };
