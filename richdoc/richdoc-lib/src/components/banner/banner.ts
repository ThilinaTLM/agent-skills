import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./banner.schema.ts";

const BANNER_ICONS: Record<string, string> = {
	draft: "edit-3",
	frozen: "snowflake",
	archived: "archive",
	confidential: "eye-off",
	info: "info",
};

const BANNER_LABELS: Record<string, string> = {
	draft: "Draft — work in progress",
	frozen: "Frozen — do not edit",
	archived: "Archived — superseded",
	confidential: "Confidential — do not circulate",
	info: "Notice",
};

/**
 * <rd-banner> — thin status ribbon for the top of a document. Renders as
 * a coloured strip with an icon and a default message determined by
 * `type`. Author-supplied text content overrides the default message.
 */
class RdBanner extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const type = this.getAttribute("type") || "info";
		this.setAttribute("data-type", type);

		// Author-provided content wins; fall back to the per-type default.
		const hasOwnContent = this.textContent && this.textContent.trim().length > 0;
		const messageOverride = this.getAttribute("message");
		const text = messageOverride || (hasOwnContent ? null : BANNER_LABELS[type] || BANNER_LABELS.info);

		const iconName = BANNER_ICONS[type] || BANNER_ICONS.info;
		const icon = document.createElement("rd-icon");
		icon.setAttribute("name", iconName);
		icon.setAttribute("size", "sm");
		icon.setAttribute("aria-hidden", "true");
		icon.className = "_rd-banner-icon";

		if (text !== null) {
			this.innerHTML = "";
			this.appendChild(icon);
			this.appendChild(el("span", { class: "_rd-banner-text" }, text));
		} else {
			// Wrap existing content in the body span so layout stays consistent.
			const wrap = el("span", { class: "_rd-banner-text" });
			while (this.firstChild) wrap.appendChild(this.firstChild);
			this.appendChild(icon);
			this.appendChild(wrap);
		}
	}
}

export function register(): void {
	define(tagName, RdBanner);
}
export { spec, tagName };
