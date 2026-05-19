import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { conSpec, conTagName, proSpec, proTagName, spec, tagName } from "./pros-cons.schema.ts";

/**
 * <rd-pros-cons> renders two adjacent columns of points with check / x
 * icons. Children must be <rd-pro> or <rd-con>. The component reflows
 * them into the two columns and prepends the appropriate icon to each.
 */
class RdProsCons extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const prosTitle = this.getAttribute("pros-title") || "Pros";
		const consTitle = this.getAttribute("cons-title") || "Cons";

		const pros = Array.from(this.querySelectorAll<HTMLElement>(":scope > rd-pro"));
		const cons = Array.from(this.querySelectorAll<HTMLElement>(":scope > rd-con"));

		this.innerHTML = "";

		const prosCol = el(
			"div",
			{ class: "_rd-pros-cons-col _rd-pros-cons-col--pros" },
			el("div", { class: "_rd-pros-cons-title" }, prosTitle),
		);
		for (const p of pros) prosCol.appendChild(p);
		const consCol = el(
			"div",
			{ class: "_rd-pros-cons-col _rd-pros-cons-col--cons" },
			el("div", { class: "_rd-pros-cons-title" }, consTitle),
		);
		for (const c of cons) consCol.appendChild(c);
		this.appendChild(prosCol);
		this.appendChild(consCol);
	}
}

function decorate(elementName: "rd-pro" | "rd-con") {
	return class extends HTMLElement {
		_upgraded = false;
		connectedCallback() {
			if ((this as unknown as { _upgraded: boolean })._upgraded) return;
			(this as unknown as { _upgraded: boolean })._upgraded = true;
			const isPro = elementName === "rd-pro";

			// Wrap the user-supplied content in a single element so it occupies
			// exactly one cell of the 2-column grid defined in pros-cons.css.
			// Without this, loose text nodes and inline children (e.g. <code>,
			// <strong>) each become their own grid item and get auto-placed
			// into the narrow icon column, overlapping nearby text.
			const content = el("div", { class: "_rd-pros-cons-content" });
			while (this.firstChild) content.appendChild(this.firstChild);

			const icon = document.createElement("rd-icon");
			icon.setAttribute("name", isPro ? "check" : "x");
			icon.setAttribute("size", "sm");
			icon.setAttribute("aria-hidden", "true");
			icon.className = "_rd-pros-cons-icon";

			this.append(icon, content);
		}
	};
}

const RdPro = decorate("rd-pro");
const RdCon = decorate("rd-con");

export function register(): void {
	define(tagName, RdProsCons);
	define(proTagName, RdPro);
	define(conTagName, RdCon);
}

export { spec, tagName, proSpec, proTagName, conSpec, conTagName };
