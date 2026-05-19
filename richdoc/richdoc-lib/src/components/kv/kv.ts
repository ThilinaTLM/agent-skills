import { define, el } from "../../lib/dom.ts";
import { rowSpec, rowTagName, spec, tagName } from "./kv.schema.ts";

interface UpgradeableRow extends HTMLElement {
	_upgraded?: boolean;
}

/**
 * <rd-kv> — magazine-style spec block.
 *
 * Two layouts:
 *   - inline   (default) — two-column grid, key on the left
 *   - stacked            — definition-list shape, term in Fraunces italic
 *                          on top of the body. Use for glossaries.
 *
 * Optional `title` renders as an eyebrow above the rows.
 */
class RdKv extends HTMLElement {
	_observer?: MutationObserver;
	_titleAttached = false;
	connectedCallback() {
		const layout = this.getAttribute("layout") || "inline";
		this.setAttribute("data-layout", layout);

		const title = this.getAttribute("title");
		if (title && !this._titleAttached) {
			this.prepend(el("div", { class: "_rd-kv-title" }, title));
			this._titleAttached = true;
		}

		this._upgradeRows();
		// Flip the layout-gate attribute only after rows are upgraded, so the
		// CSS grid never paints against an incomplete DOM (pre-upgrade rows
		// have no _rd-kv-key div, which would otherwise produce a one-cell
		// shift on first paint).
		this.setAttribute("data-upgraded", "");
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
			row.setAttribute("data-upgraded", "");
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
