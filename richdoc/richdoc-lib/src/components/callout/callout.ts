import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { CALLOUT_ICONS } from "./callout-icons.ts";
import { spec, tagName } from "./callout.schema.ts";

// Default titles per type. Most types title-case the type name; the
// `tldr` type spells out its acronym.
const CALLOUT_TITLES: Record<string, string> = {
	tldr: "TL;DR",
};

class RdCallout extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const type = this.getAttribute("type") || "info";
		const title = this.getAttribute("title");
		const titleText = title || CALLOUT_TITLES[type] || type.charAt(0).toUpperCase() + type.slice(1);

		// tldr is a summary band, not an attention block — no icon.
		const titleChildren: (HTMLElement | string)[] = [];
		if (type !== "tldr") {
			const iconName = CALLOUT_ICONS[type] || CALLOUT_ICONS.info;
			const icon = el("span", { class: "_rd-callout-icon", "aria-hidden": "true" });
			const iconTag = document.createElement("rd-icon");
			iconTag.setAttribute("name", iconName);
			iconTag.setAttribute("size", "md");
			icon.appendChild(iconTag);
			titleChildren.push(icon);
		}
		titleChildren.push(el("span", { class: "_rd-callout-text" }, titleText));

		// Wrap the slotted body (everything currently inside this element) in a
		// single _rd-callout-body div, then prepend the title. This guarantees
		// exactly two direct children — title + body — so the TL;DR variant's
		// `display: grid` host always lays out as [title | body] regardless of
		// whether the author wrapped the body in <p>, used mixed inline content,
		// or wrote bare text. Layout-neutral for non-tldr (display: block)
		// variants; uniform DOM shape simplifies CSS and lint reasoning.
		const body = el("div", { class: "_rd-callout-body" });
		while (this.firstChild) body.appendChild(this.firstChild);
		this.appendChild(el("div", { class: "_rd-callout-title" }, ...titleChildren));
		this.appendChild(body);

		// Warn/danger callouts fire a one-shot pulse on the icon when they
		// enter view. Info/success/note/tldr stay neutral — motion is
		// reserved for callouts that genuinely demand attention.
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
