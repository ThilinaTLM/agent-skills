import { type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tagName } from "./figure.schema.ts";

class RdFigure extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const caption = this.getAttribute("caption");
		if (caption) {
			this.appendChild(el("figcaption", { class: "_rd-figure-cap" }, caption));
		}
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdFigure);
}
export { spec, tagName };
