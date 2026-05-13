import { ICONS, type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tagName } from "./callout.schema.ts";

class RdCallout extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const type = this.getAttribute("type") || "info";
		const title = this.getAttribute("title");
		const icon = ICONS[type] || ICONS.info;
		const titleText = title || type.charAt(0).toUpperCase() + type.slice(1);
		this.prepend(
			el(
				"div",
				{ class: "_rd-callout-title" },
				el("span", { class: "_rd-callout-icon", "aria-hidden": "true" }, icon),
				titleText,
			),
		);
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdCallout);
}
export { spec, tagName };
