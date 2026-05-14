import { type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tagName } from "./sidenote.schema.ts";

class RdSidenote extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const mark = this.getAttribute("mark");
		const marker = el("span", { class: "_rd-sidenote-marker" });
		if (mark) {
			marker.textContent = mark;
			marker.setAttribute("data-custom-mark", "");
		}
		const body = el("span", { class: "_rd-sidenote-body" });
		while (this.firstChild) body.appendChild(this.firstChild);
		this.appendChild(marker);
		this.appendChild(body);
	}
}

export function register(): void {
	define(tagName, RdSidenote);
}
export { spec, tagName };
