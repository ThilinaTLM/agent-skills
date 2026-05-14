import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { spec, tagName } from "./tldr.schema.ts";

/**
 * <rd-tldr> — a focal "too long; didn't read" strip. Distinct visual
 * identity from <rd-callout>: oversized eyebrow, slightly larger body,
 * full-width band. Usually the first block after <rd-hero> or <h1>.
 */
class RdTldr extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const label = this.getAttribute("label") || "TL;DR";
		const body = el("div", { class: "_rd-tldr-body" });
		while (this.firstChild) body.appendChild(this.firstChild);
		this.appendChild(el("div", { class: "_rd-tldr-label" }, label));
		this.appendChild(body);
		reveal(this);
	}
}

export function register(): void {
	define(tagName, RdTldr);
}
export { spec, tagName };
