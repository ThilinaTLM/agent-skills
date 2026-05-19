import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { attachTooltip } from "./tooltip-service.ts";
import { spec, tagName } from "./tooltip.schema.ts";

/**
 * <rd-tooltip term="API">rich body...</rd-tooltip>
 *
 * Inline definition popup. The `term` attribute renders as the visible
 * trigger with a dotted-underline affordance; the element's children
 * render as a rich tooltip body on hover, focus, or tap.
 */
class RdTooltip extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;

		const term = this.getAttribute("term");
		if (!term) return; // Schema requires term; bail silently if missing.

		const placementAttr = this.getAttribute("placement");
		const placement =
			placementAttr === "top" || placementAttr === "bottom" ? placementAttr : "auto";

		// Move existing children into a detached content container.
		const content = el("div", { class: "_rd-tooltip-content" });
		while (this.firstChild) content.appendChild(this.firstChild);

		// Build the inline trigger span.
		const trigger = el("span", { class: "_rd-tooltip-trigger", tabindex: "0" }, term);
		this.appendChild(trigger);

		attachTooltip(trigger, content, {
			clickToToggle: true,
			placement,
		});
	}
}

export function register(): void {
	define(tagName, RdTooltip);
}
export { spec, tagName };
