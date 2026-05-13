import { define, el } from "../../lib/base.ts";
import { rowSpec, rowTagName, spec, tagName } from "./kv.schema.ts";

interface UpgradeableRow extends HTMLElement {
	_upgraded?: boolean;
}

class RdKv extends HTMLElement {
	_observer?: MutationObserver;
	connectedCallback() {
		this._upgradeRows();
		if (!this._observer) {
			this._observer = new MutationObserver(() => this._upgradeRows());
			this._observer.observe(this, { childList: true });
		}
	}
	disconnectedCallback() {
		this._observer?.disconnect();
		this._observer = undefined;
	}
	_upgradeRows() {
		const rows = this.querySelectorAll<UpgradeableRow>(":scope > rd-row");
		for (const row of rows) {
			if (row._upgraded) continue;
			const key = row.getAttribute("key") || "";
			const valueWrap = el("div", { class: "_rd-kv-value" });
			while (row.firstChild) valueWrap.appendChild(row.firstChild);
			row.appendChild(el("div", { class: "_rd-kv-key" }, key));
			row.appendChild(valueWrap);
			row._upgraded = true;
		}
	}
}

class RdRow extends HTMLElement {
	// Upgrade is driven by parent (rd-kv).
}

export function register(): void {
	define(tagName, RdKv);
	define(rowTagName, RdRow);
}

export { spec, tagName, rowSpec, rowTagName };
