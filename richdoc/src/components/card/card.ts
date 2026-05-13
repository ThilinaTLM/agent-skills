import { type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tagName } from "./card.schema.ts";

class RdCard extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const title = this.getAttribute("title");
		if (title) this.prepend(el("div", { class: "_rd-card-header" }, title));
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdCard);
}
export { spec, tagName };
