import { type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tagName } from "./card.schema.ts";

class RdCard extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const title = this.getAttribute("title");
		const accent = this.getAttribute("accent");
		if (!title && !accent) return;
		const header = el("div", { class: "_rd-card-header" });
		if (accent && accent !== "muted") {
			header.appendChild(el("span", { class: "_rd-card-kicker" }, accent));
		}
		if (title) {
			header.appendChild(el("span", { class: "_rd-card-title" }, title));
		}
		if (header.childNodes.length > 0) {
			this.prepend(header);
		}
	}
}

export function register(): void {
	define(tagName, RdCard);
}
export { spec, tagName };
