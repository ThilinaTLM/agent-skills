import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { type Row, parseData, parseValues } from "./chart-data.ts";
import { spec, tagName } from "./chart.schema.ts";
import { type PlotApi, loadPlot } from "./plot-loader.ts";

/**
 * <rd-chart> — SVG chart powered by Observable Plot.
 *
 * The element's content is the data payload (JSON or CSV). Attributes
 * describe the chart kind and the column mapping. Plot is lazy-loaded
 * from jsDelivr on first use; if it fails, we render a <table> so the
 * data remains readable offline.
 */

const CHART_PALETTE = [
	"var(--rd-accent)",
	"var(--rd-info)",
	"var(--rd-success)",
	"var(--rd-warn)",
	"var(--rd-danger)",
	"var(--rd-note)",
];

class RdChart extends HTMLElement implements Upgradeable {
	_upgraded = false;
	_resizeObserver: ResizeObserver | null = null;
	_lastWidth = 0;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const variant = this.getAttribute("variant") || "chart";
		if (variant === "sparkline") {
			this.setAttribute("data-variant", "sparkline");
			await renderSparkline(this);
			return;
		}
		const kind = this.getAttribute("kind") || "bar";
		const format = (this.getAttribute("format") || "auto") as "json" | "csv" | "auto";
		const xAttr = this.getAttribute("x");
		const yAttr = this.getAttribute("y");
		const seriesAttr = this.getAttribute("series");
		const valuesAttr = this.getAttribute("data");
		const labelsAttr = this.getAttribute("labels");
		const title = this.getAttribute("title");
		const caption = this.getAttribute("caption");
		const height = Number(this.getAttribute("height") || "320");
		const showLegend = this.getAttribute("legend") !== "false";

		// Choose data source: explicit values list, `data` attribute, or text content.
		let rows: Row[] = [];
		let xKey = xAttr || "label";
		let yKey = yAttr || "value";

		if (valuesAttr && /^[\d\s,.\-eE]+$/.test(valuesAttr)) {
			rows = parseValues(valuesAttr, labelsAttr);
			xKey = "label";
			yKey = "value";
		} else if (valuesAttr) {
			rows = parseData(valuesAttr, format);
		} else {
			rows = parseData(this.textContent || "", format);
		}

		this.innerHTML = "";

		// Header (title) + body container.
		if (title) this.appendChild(el("div", { class: "_rd-chart-title" }, title));
		const body = el("div", { class: "_rd-chart-body", style: `min-height:${height}px` });
		this.appendChild(body);
		if (caption) this.appendChild(el("div", { class: "_rd-chart-caption" }, caption));

		if (!rows.length) {
			body.appendChild(el("div", { class: "_rd-chart-fallback" }, "No data."));
			return;
		}

		const plot = await loadPlot();
		if (!plot) {
			body.appendChild(buildTable(rows));
			return;
		}

		const paint = (width: number): void => {
			if (width < 80) return; // skip jitter while invisible
			if (Math.abs(width - this._lastWidth) < 8) return; // debounce
			this._lastWidth = width;
			try {
				const node = renderPlot(plot, kind, rows, {
					x: xKey,
					y: yKey,
					series: seriesAttr || null,
					width,
					height,
					showLegend,
				});
				body.innerHTML = "";
				body.appendChild(node);
			} catch (err) {
				console.warn("[richdoc] chart render failed:", err);
				body.innerHTML = "";
				body.appendChild(buildTable(rows));
			}
		};

		// Initial paint: use the body's measured width (post-layout). Then
		// observe for width changes (picker switch, viewport resize, parent
		// rd-cols collapse) and re-render. Debounced via the diff check in
		// `paint` so the observer can fire freely.
		const initial = Math.round(body.getBoundingClientRect().width) || 640;
		paint(initial);
		this._resizeObserver = new ResizeObserver((entries) => {
			const w = Math.round(entries[0]?.contentRect.width ?? 0);
			paint(w);
		});
		this._resizeObserver.observe(body);

		reveal(this);
	}
	disconnectedCallback() {
		this._resizeObserver?.disconnect();
		this._resizeObserver = null;
	}
}

interface RenderOpts {
	x: string;
	y: string;
	series: string | null;
	width: number;
	height: number;
	showLegend: boolean;
}

function renderPlot(
	Plot: PlotApi,
	kind: string,
	rows: Row[],
	opts: RenderOpts,
): SVGElement | HTMLElement {
	const { x, y, series, width, height, showLegend } = opts;

	const base: Record<string, unknown> = {
		width,
		height,
		marginLeft: 60,
		marginRight: 24,
		marginTop: 24,
		marginBottom: 40,
		style: {
			background: "transparent",
			color: "var(--rd-fg)",
			fontFamily: "var(--rd-font-body)",
			fontSize: "12px",
			overflow: "visible",
		},
		color: { range: CHART_PALETTE },
	};
	if (showLegend && series) base.color = { ...(base.color as object), legend: true };

	const inferQuant = (key: string): boolean => rows.some((r) => typeof r[key] === "number");
	const yIsQuant = inferQuant(y);
	const xIsQuant = inferQuant(x);

	const marks: unknown[] = [];

	if (kind === "bar") {
		const opts: Record<string, unknown> = { y, fill: series ?? "var(--rd-accent)" };
		if (xIsQuant && !yIsQuant) {
			// Horizontal bars: numeric x, categorical y
			marks.push(Plot.barX(rows, { x, y, fill: series ?? "var(--rd-accent)" }));
		} else {
			opts.x = x;
			marks.push(Plot.barY(rows, opts));
		}
		marks.push(Plot.ruleY([0]));
	} else if (kind === "line") {
		marks.push(
			Plot.line(rows, {
				x,
				y,
				stroke: series ?? "var(--rd-accent)",
				strokeWidth: 1.75,
			}),
		);
	} else if (kind === "area") {
		marks.push(
			Plot.areaY(rows, {
				x,
				y,
				fill: series ?? "var(--rd-accent)",
				fillOpacity: 0.35,
			}),
		);
		marks.push(
			Plot.line(rows, {
				x,
				y,
				stroke: series ?? "var(--rd-accent)",
				strokeWidth: 1.5,
			}),
		);
		marks.push(Plot.ruleY([0]));
	} else if (kind === "scatter") {
		marks.push(
			Plot.dot(rows, {
				x,
				y,
				fill: series ?? "var(--rd-accent)",
				r: 4,
			}),
		);
	} else if (kind === "heatmap") {
		marks.push(
			Plot.cell(rows, {
				x,
				y,
				fill: y,
				inset: 0.5,
			}),
		);
	} else if (kind === "donut") {
		// Plot doesn't ship a pie/donut primitive. Render an SVG donut by hand
		// using d3-arc via Plot's d3 dependency. Fall back to a bar chart
		// representation if anything fails.
		const w = Math.max(160, Math.min(width, 480));
		const h = height;
		const total = rows.reduce(
			(acc, r) => acc + (typeof r[y] === "number" ? (r[y] as number) : 0),
			0,
		);
		if (total <= 0) return buildTable(rows);
		const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
		svg.setAttribute("style", "max-width:100%;height:auto");
		const cx = w / 2;
		const cy = h / 2;
		const radius = Math.min(w, h) / 2 - 12;
		const inner = radius * 0.6;
		let start = -Math.PI / 2;
		rows.forEach((r, i) => {
			const v = (r[y] as number) ?? 0;
			if (!v) return;
			const angle = (v / total) * 2 * Math.PI;
			const end = start + angle;
			const path = donutArc(cx, cy, radius, inner, start, end);
			const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
			p.setAttribute("d", path);
			p.setAttribute("fill", CHART_PALETTE[i % CHART_PALETTE.length]);
			p.setAttribute("stroke", "var(--rd-bg-elev)");
			p.setAttribute("stroke-width", "2");
			svg.appendChild(p);
			start = end;
		});
		return svg;
	}

	return Plot.plot({ ...base, marks });
}

function donutArc(
	cx: number,
	cy: number,
	r: number,
	rInner: number,
	a0: number,
	a1: number,
): string {
	const x0 = cx + r * Math.cos(a0);
	const y0 = cy + r * Math.sin(a0);
	const x1 = cx + r * Math.cos(a1);
	const y1 = cy + r * Math.sin(a1);
	const x2 = cx + rInner * Math.cos(a1);
	const y2 = cy + rInner * Math.sin(a1);
	const x3 = cx + rInner * Math.cos(a0);
	const y3 = cy + rInner * Math.sin(a0);
	const large = a1 - a0 > Math.PI ? 1 : 0;
	return `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} L ${x2} ${y2} A ${rInner} ${rInner} 0 ${large} 0 ${x3} ${y3} Z`;
}

function buildTable(rows: Row[]): HTMLElement {
	const keys = Object.keys(rows[0] ?? {});
	const table = el("table", { class: "_rd-chart-table" });
	const thead = el("thead");
	const trH = el("tr");
	for (const k of keys) trH.appendChild(el("th", {}, k));
	thead.appendChild(trH);
	table.appendChild(thead);
	const tbody = el("tbody");
	for (const r of rows) {
		const tr = el("tr");
		for (const k of keys) {
			const v = r[k];
			tr.appendChild(el("td", {}, v === undefined || v === null ? "" : String(v)));
		}
		tbody.appendChild(tr);
	}
	table.appendChild(tbody);
	return table;
}

/**
 * Sparkline mode — inline trend strip, no chrome. Same Plot engine,
 * different defaults and a strictly minimal layout. Triggered by
 * `variant="sparkline"`.
 */
async function renderSparkline(host: HTMLElement): Promise<void> {
	const raw = host.getAttribute("data") || host.textContent || "";
	const values = raw
		.split(",")
		.map((s) => s.trim())
		.filter(Boolean)
		.map(Number)
		.filter((n) => Number.isFinite(n));
	host.innerHTML = "";
	if (!values.length) return;

	const kind = host.getAttribute("kind") || "line";
	const width = Number(host.getAttribute("width") || "80");
	const height = Number(host.getAttribute("height") || "20");
	const color = host.getAttribute("color") || "currentColor";
	const showEndpoint = host.getAttribute("endpoint") !== "false";

	const Plot = await loadPlot();
	if (!Plot) {
		host.appendChild(el("span", { class: "_rd-sparkline-fallback" }, sparkSummary(values)));
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
		host.appendChild(svg);
	} catch {
		host.appendChild(el("span", { class: "_rd-sparkline-fallback" }, sparkSummary(values)));
	}
}

function sparkSummary(vs: number[]): string {
	const last = vs[vs.length - 1];
	const first = vs[0];
	const delta = last - first;
	const sign = delta > 0 ? "▲" : delta < 0 ? "▼" : "→";
	return `${sign} ${formatSparkNum(last)}`;
}

function formatSparkNum(n: number): string {
	if (Number.isInteger(n)) return String(n);
	return n.toFixed(1);
}

export function register(): void {
	define(tagName, RdChart);
}
export { spec, tagName };
