import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { loadPlot } from "../chart/plot-loader.ts";
import { spec, tagName } from "./sparkline.schema.ts";

/**
 * <rd-sparkline> — tiny inline trend. Same Plot engine as <rd-chart>,
 * stripped of axes / labels / chrome. Works in tables, prose, captions,
 * and inside <rd-stat>.
 */
class RdSparkline extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const raw = this.getAttribute("values") || "";
		const values = raw
			.split(",")
			.map((s) => s.trim())
			.filter(Boolean)
			.map(Number)
			.filter((n) => Number.isFinite(n));
		const kind = this.getAttribute("kind") || "line";
		const width = Number(this.getAttribute("width") || "80");
		const height = Number(this.getAttribute("height") || "20");
		const color = this.getAttribute("color") || "currentColor";
		const showEndpoint = this.getAttribute("endpoint") !== "false";

		if (!values.length) return;

		const Plot = await loadPlot();
		if (!Plot) {
			// Fallback: tiny inline summary
			this.appendChild(el("span", { class: "_rd-sparkline-fallback" }, summary(values)));
			return;
		}

		const data = values.map((v, i) => ({ i, v }));
		const opts: Record<string, unknown> = {
			width,
			height,
			marginTop: 2,
			marginBottom: 2,
			marginLeft: 2,
			marginRight: showEndpoint ? 6 : 2,
			x: { axis: null },
			y: { axis: null },
			style: {
				background: "transparent",
				overflow: "visible",
			},
			marks: [
				kind === "bar"
					? Plot.barY(data, { x: "i", y: "v", fill: color })
					: kind === "area"
						? Plot.areaY(data, { x: "i", y: "v", fill: color, fillOpacity: 0.25 })
						: Plot.line(data, { x: "i", y: "v", stroke: color, strokeWidth: 1.25 }),
			],
		};
		if (showEndpoint && kind !== "bar") {
			(opts.marks as unknown[]).push(
				Plot.dot([data[data.length - 1]], { x: "i", y: "v", fill: color, r: 2 }),
			);
		}
		try {
			const svg = Plot.plot(opts);
			this.innerHTML = "";
			this.appendChild(svg);
		} catch {
			this.appendChild(el("span", { class: "_rd-sparkline-fallback" }, summary(values)));
		}
	}
}

function summary(vs: number[]): string {
	const last = vs[vs.length - 1];
	const first = vs[0];
	const delta = last - first;
	const sign = delta > 0 ? "▲" : delta < 0 ? "▼" : "→";
	return `${sign} ${formatNum(last)}`;
}

function formatNum(n: number): string {
	if (Number.isInteger(n)) return String(n);
	return n.toFixed(1);
}

export function register(): void {
	define(tagName, RdSparkline);
}
export { spec, tagName };
