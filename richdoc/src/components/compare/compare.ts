import { type Upgradeable, define, el } from "../../lib/base.ts";
import {
	cellSpec,
	cellTagName,
	rowCellsSpec,
	rowCellsTagName,
	spec,
	tagName,
} from "./compare.schema.ts";

class RdCompare extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const headersAttr = this.getAttribute("headers") || "";
		const headers = headersAttr
			.split(",")
			.map((s) => s.trim())
			.filter(Boolean);

		const rows = Array.from(this.querySelectorAll<HTMLElement>(":scope > rd-row-cells"));

		const thead = el("thead", {}, el("tr", {}, ...headers.map((h) => el("th", {}, h))));
		const tbody = el("tbody");

		for (const r of rows) {
			const label = r.getAttribute("label") || "";
			const cells = Array.from(r.querySelectorAll<HTMLElement>(":scope > rd-cell"));
			const tr = el("tr");
			tr.appendChild(el("td", {}, label));
			for (const c of cells) {
				const td = el("td");
				const tone = c.getAttribute("tone");
				if (tone) td.setAttribute("data-tone", tone);
				while (c.firstChild) td.appendChild(c.firstChild);
				tr.appendChild(td);
			}
			tbody.appendChild(tr);
		}

		this.innerHTML = "";
		this.appendChild(el("table", { class: "_rd-compare-table" }, thead, tbody));
		this._upgraded = true;
	}
}

class RdRowCells extends HTMLElement {}
class RdCell extends HTMLElement {}

export function register(): void {
	define(tagName, RdCompare);
	define(rowCellsTagName, RdRowCells);
	define(cellTagName, RdCell);
}

export { spec, tagName, rowCellsSpec, rowCellsTagName, cellSpec, cellTagName };
