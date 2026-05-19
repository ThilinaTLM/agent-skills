import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { itemSpec, itemTagName, laneSpec, laneTagName, spec, tagName } from "./roadmap.schema.ts";

/**
 * <rd-roadmap> — quarter × workstream horizon view.
 *
 * Rendered as a self-contained, theme-aware CSS grid. Every bar is
 * absolutely positioned by percentage inside its lane track, so the chart
 * fits the page width without horizontal scroll and never needs a heavy
 * external Gantt library. The axis adapts to the configured time unit
 * (day / week / month / quarter) and a discreet "today" marker is drawn
 * when the current date falls inside the window.
 */

type Unit = "day" | "week" | "month" | "quarter";

interface RoadmapItem {
	id: string;
	label: string;
	start: number; // ms epoch
	end: number; // ms epoch
	progress: number; // 0..1
	tone: string | null;
	lane: string;
}

interface ParsedSpan {
	start: number;
	end: number;
}

class RdRoadmap extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;

		const span = parseSpan(this.getAttribute("start") || "", this.getAttribute("end") || "");
		const unit = (this.getAttribute("unit") || "month") as Unit;
		const title = this.getAttribute("title");

		const lanes = collectLanes(this);

		this.innerHTML = "";
		if (title) this.appendChild(el("div", { class: "_rd-roadmap-title" }, title));

		if (!span || !lanes.length) {
			this.appendChild(el("div", { class: "_rd-roadmap-fallback" }, "No roadmap items to render."));
			reveal(this);
			return;
		}

		this.appendChild(buildChart(span, unit, lanes));
		reveal(this);
	}
}

function parseSpan(start: string, end: string): ParsedSpan | null {
	const s = Date.parse(start);
	const e = Date.parse(end);
	if (!Number.isFinite(s) || !Number.isFinite(e) || e <= s) return null;
	return { start: s, end: e };
}

interface Lane {
	name: string;
	items: RoadmapItem[];
}

function collectLanes(root: HTMLElement): Lane[] {
	const laneEls = Array.from(root.querySelectorAll<HTMLElement>(":scope > rd-lane"));
	const lanes: Lane[] = [];
	let counter = 0;
	for (const laneEl of laneEls) {
		const name = laneEl.getAttribute("name") || "";
		const itemEls = Array.from(laneEl.querySelectorAll<HTMLElement>(":scope > rd-item"));
		const items: RoadmapItem[] = [];
		for (const itEl of itemEls) {
			const startRaw = itEl.getAttribute("start") || "";
			const endRaw = itEl.getAttribute("end") || "";
			const label = itEl.getAttribute("label") || "";
			const start = Date.parse(startRaw);
			const end = Date.parse(endRaw);
			if (!label || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
				continue;
			}
			const progress = clamp01(Number(itEl.getAttribute("progress") || "0"));
			items.push({
				id: `rd-roadmap-${++counter}`,
				label,
				start,
				end,
				progress,
				tone: itEl.getAttribute("tone"),
				lane: name,
			});
		}
		if (items.length) lanes.push({ name, items });
	}
	return lanes;
}

function buildChart(span: ParsedSpan, unit: Unit, lanes: Lane[]): HTMLElement {
	const chart = el("div", { class: "_rd-roadmap-chart" });

	// Axis row: spans the same track grid as each lane so columns align.
	const axis = el("div", { class: "_rd-roadmap-axis" });
	axis.appendChild(el("div", { class: "_rd-roadmap-axis-name" })); // empty header for the lane-name column
	const axisTrack = el("div", { class: "_rd-roadmap-axis-track" });
	for (const tick of axisTicks(span, unit)) {
		const node = el("div", {
			class: "_rd-roadmap-axis-tick",
			style: `--rd-tick-pos:${(tick.position * 100).toFixed(3)}%`,
		});
		node.appendChild(el("span", { class: "_rd-roadmap-axis-label" }, tick.label));
		axisTrack.appendChild(node);
	}
	const today = todayMarker(span);
	if (today != null) {
		axisTrack.appendChild(
			el("div", {
				class: "_rd-roadmap-today",
				style: `--rd-today-pos:${(today * 100).toFixed(3)}%`,
				title: "Today",
			}),
		);
	}
	axis.appendChild(axisTrack);
	chart.appendChild(axis);

	for (const lane of lanes) {
		chart.appendChild(buildLane(span, lane, today));
	}
	return chart;
}

function buildLane(span: ParsedSpan, lane: Lane, today: number | null): HTMLElement {
	const row = el("div", { class: "_rd-roadmap-lane" });
	row.appendChild(el("div", { class: "_rd-roadmap-lane-name" }, lane.name));
	const track = el("div", { class: "_rd-roadmap-lane-track" });
	if (today != null) {
		track.appendChild(
			el("div", {
				class: "_rd-roadmap-today _rd-roadmap-today-line",
				style: `--rd-today-pos:${(today * 100).toFixed(3)}%`,
			}),
		);
	}
	for (const item of lane.items) {
		track.appendChild(buildBar(span, item));
	}
	row.appendChild(track);
	return row;
}

function buildBar(span: ParsedSpan, item: RoadmapItem): HTMLElement {
	const total = span.end - span.start;
	const left = clamp01((item.start - span.start) / total);
	const right = clamp01(1 - (item.end - span.start) / total);
	const bar = el("div", {
		class: "_rd-roadmap-bar",
		style: `--rd-bar-left:${(left * 100).toFixed(3)}%; --rd-bar-right:${(right * 100).toFixed(3)}%; --rd-bar-progress:${Math.round(item.progress * 100)}%`,
		"data-tone": item.tone || "",
		title: `${item.label} — ${fmtDate(item.start)} → ${fmtDate(item.end)}${item.progress > 0 ? ` · ${Math.round(item.progress * 100)}%` : ""}`,
	});
	bar.appendChild(el("span", { class: "_rd-roadmap-bar-fill" }));
	bar.appendChild(el("span", { class: "_rd-roadmap-bar-label" }, item.label));
	return bar;
}

interface Tick {
	position: number;
	label: string;
}

function axisTicks(span: ParsedSpan, unit: Unit): Tick[] {
	const total = span.end - span.start;
	const start = new Date(span.start);
	const ticks: Tick[] = [];
	const push = (date: Date, label: string) => {
		const t = date.getTime();
		if (t < span.start || t > span.end) return;
		ticks.push({ position: (t - span.start) / total, label });
	};
	if (unit === "day") {
		const cur = new Date(start);
		cur.setHours(0, 0, 0, 0);
		while (cur.getTime() <= span.end) {
			push(new Date(cur), cur.toLocaleDateString(undefined, { day: "numeric", month: "short" }));
			cur.setDate(cur.getDate() + 1);
		}
	} else if (unit === "week") {
		const cur = new Date(start);
		cur.setHours(0, 0, 0, 0);
		// Snap to Monday.
		const dow = (cur.getDay() + 6) % 7;
		cur.setDate(cur.getDate() - dow);
		while (cur.getTime() <= span.end) {
			push(new Date(cur), cur.toLocaleDateString(undefined, { day: "numeric", month: "short" }));
			cur.setDate(cur.getDate() + 7);
		}
	} else if (unit === "quarter") {
		const cur = new Date(start.getFullYear(), Math.floor(start.getMonth() / 3) * 3, 1);
		while (cur.getTime() <= span.end) {
			const q = Math.floor(cur.getMonth() / 3) + 1;
			push(new Date(cur), `Q${q} ${cur.getFullYear()}`);
			cur.setMonth(cur.getMonth() + 3);
		}
	} else {
		// month
		const cur = new Date(start.getFullYear(), start.getMonth(), 1);
		while (cur.getTime() <= span.end) {
			const label =
				cur.getMonth() === 0
					? `${cur.toLocaleString(undefined, { month: "short" })} ${cur.getFullYear()}`
					: cur.toLocaleString(undefined, { month: "short" });
			push(new Date(cur), label);
			cur.setMonth(cur.getMonth() + 1);
		}
	}
	return ticks;
}

function todayMarker(span: ParsedSpan): number | null {
	const now = Date.now();
	if (now < span.start || now > span.end) return null;
	return (now - span.start) / (span.end - span.start);
}

function fmtDate(ms: number): string {
	return new Date(ms).toLocaleDateString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
	});
}

function clamp01(n: number): number {
	if (!Number.isFinite(n)) return 0;
	if (n < 0) return 0;
	if (n > 1) return 1;
	return n;
}

class RdLane extends HTMLElement {}
class RdItem extends HTMLElement {}

export function register(): void {
	define(tagName, RdRoadmap);
	define(laneTagName, RdLane);
	define(itemTagName, RdItem);
}

export { spec, tagName, laneSpec, laneTagName, itemSpec, itemTagName };
