import { type Upgradeable, define, el } from "../../lib/dom.ts";
import {
	criterionSpec,
	criterionTagName,
	scoreSpec,
	scoreTagName,
	spec,
	tagName,
} from "./rubric.schema.ts";

/**
 * <rd-rubric> — weighted scoring grid for comparison/evaluation docs.
 *
 *   <rd-rubric options="Postgres,SQLite,DynamoDB" scale="5">
 *     <rd-criterion label="Ops cost" weight="2">
 *       <rd-score value="3">paid hosting</rd-score>
 *       <rd-score value="5">free, local</rd-score>
 *       <rd-score value="4">pay-per-use</rd-score>
 *     </rd-criterion>
 *     …
 *   </rd-rubric>
 *
 * Each row is a criterion. Scores must appear in the same order as
 * `options`. A weighted total row is rendered at the bottom; the winning
 * column gets a subtle accent stripe.
 */
class RdRubric extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const optionsAttr = this.getAttribute("options") || "";
		const options = optionsAttr
			.split(",")
			.map((s) => s.trim())
			.filter(Boolean);
		const scale = Number(this.getAttribute("scale") || "5");
		const title = this.getAttribute("title");

		const criteria = Array.from(this.querySelectorAll<HTMLElement>(":scope > rd-criterion"));
		const totals = options.map(() => 0);

		// Header
		const headerCells: HTMLElement[] = [el("th", { class: "_rd-rubric-th-corner" }, "Criterion")];
		for (const opt of options) headerCells.push(el("th", {}, opt));
		const thead = el("thead", {}, el("tr", {}, ...headerCells));

		// Body
		const tbody = el("tbody");
		for (const c of criteria) {
			const label = c.getAttribute("label") || "";
			const weight = Number(c.getAttribute("weight") || "1");
			const scores = Array.from(c.querySelectorAll<HTMLElement>(":scope > rd-score"));
			const tr = el("tr");
			tr.appendChild(
				el(
					"td",
					{ class: "_rd-rubric-criterion" },
					el("div", { class: "_rd-rubric-criterion-label" }, label),
					weight !== 1
						? el(
								"div",
								{ class: "_rd-rubric-criterion-weight" },
								`weight × ${formatNum(weight)}`,
							)
						: null,
				),
			);
			for (let i = 0; i < options.length; i++) {
				const sEl = scores[i];
				const raw = sEl?.getAttribute("value");
				const v = raw !== null && raw !== undefined ? Number(raw) : Number.NaN;
				if (Number.isFinite(v)) totals[i] += v * weight;
				const note = sEl?.getAttribute("note");
				const noteChildren = sEl ? Array.from(sEl.childNodes) : [];
				const cell = el(
					"td",
					{ class: "_rd-rubric-cell" },
					el(
						"div",
						{ class: "_rd-rubric-score" },
						Number.isFinite(v) ? formatNum(v) : "—",
						el("span", { class: "_rd-rubric-score-of" }, `/${scale}`),
					),
				);
				renderBar(cell, Number.isFinite(v) ? v / scale : 0);
				if (note) cell.appendChild(el("div", { class: "_rd-rubric-note" }, note));
				if (noteChildren.length) {
					const body = el("div", { class: "_rd-rubric-cell-body" });
					for (const n of noteChildren) body.appendChild(n);
					cell.appendChild(body);
				}
				tr.appendChild(cell);
			}
			tbody.appendChild(tr);
		}

		// Totals row
		const max = Math.max(...totals);
		const tfoot = el(
			"tfoot",
			{},
			el(
				"tr",
				{},
				el("td", { class: "_rd-rubric-total-label" }, "Total"),
				...totals.map((t, i) =>
					el(
						"td",
						{
							class: "_rd-rubric-total",
							"data-winner": totals.length > 1 && t === max && max > 0 ? "true" : "false",
						},
						formatNum(t),
					),
				),
			),
		);

		this.innerHTML = "";
		if (title) this.appendChild(el("div", { class: "_rd-rubric-title" }, title));
		this.appendChild(el("table", { class: "_rd-rubric-table" }, thead, tbody, tfoot));
	}
}

function renderBar(cell: HTMLElement, frac: number): void {
	const bar = el("div", { class: "_rd-rubric-bar" });
	const fill = el("div", { class: "_rd-rubric-bar-fill" });
	fill.style.width = `${Math.max(0, Math.min(1, frac)) * 100}%`;
	bar.appendChild(fill);
	cell.appendChild(bar);
}

function formatNum(n: number): string {
	if (!Number.isFinite(n)) return "—";
	if (Number.isInteger(n)) return String(n);
	return n.toFixed(1);
}

class RdCriterion extends HTMLElement {}
class RdScore extends HTMLElement {}

export function register(): void {
	define(tagName, RdRubric);
	define(criterionTagName, RdCriterion);
	define(scoreTagName, RdScore);
}

export {
	spec,
	tagName,
	criterionSpec,
	criterionTagName,
	scoreSpec,
	scoreTagName,
};
