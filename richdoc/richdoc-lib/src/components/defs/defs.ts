import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { defSpec, defTagName, spec, tagName } from "./defs.schema.ts";

class RdDefs extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const title = this.getAttribute("title");
		if (title) {
			this.prepend(el("div", { class: "_rd-defs-title" }, title));
		}
	}
}

class RdDef extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const term = this.getAttribute("term") || "";
		const body = el("dd", { class: "_rd-def-body" });
		while (this.firstChild) body.appendChild(this.firstChild);
		const termEl = el("dt", { class: "_rd-def-term" }, term);
		this.appendChild(termEl);
		this.appendChild(body);
	}
}

export function register(): void {
	define(tagName, RdDefs);
	define(defTagName, RdDef);
}
export { spec, tagName, defSpec, defTagName };
