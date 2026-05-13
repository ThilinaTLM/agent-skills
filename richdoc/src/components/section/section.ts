import { type Upgradeable, define, el, slugify } from "../../lib/base.ts";
import { spec, tagName } from "./section.schema.ts";

class RdSection extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const title = this.getAttribute("title");
		if (!title) {
			this._upgraded = true;
			return;
		}
		const id =
			this.getAttribute("id") ||
			slugify(title) ||
			`section-${Math.random().toString(36).slice(2, 7)}`;
		this.setAttribute("id", id);
		this.prepend(el("h2", { class: "_rd-section-title" }, title));
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdSection);
}
export { spec, tagName };
