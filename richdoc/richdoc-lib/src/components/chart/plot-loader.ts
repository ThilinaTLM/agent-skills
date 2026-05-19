import { loadCdnScript } from "../../lib/cdn.ts";

const D3_URL = "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js";
const PLOT_URL = "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/dist/plot.umd.min.js";

// Loose Plot type covering what we use. Plot exposes the same surface
// in its UMD build and on `window.Plot`.
export interface PlotApi {
	plot: (opts: Record<string, unknown>) => SVGElement | HTMLElement;
	barX: (data: unknown, opts: Record<string, unknown>) => unknown;
	barY: (data: unknown, opts: Record<string, unknown>) => unknown;
	line: (data: unknown, opts: Record<string, unknown>) => unknown;
	lineY: (data: unknown, opts: Record<string, unknown>) => unknown;
	areaY: (data: unknown, opts: Record<string, unknown>) => unknown;
	dot: (data: unknown, opts: Record<string, unknown>) => unknown;
	cell: (data: unknown, opts: Record<string, unknown>) => unknown;
	ruleY: (data: unknown[] | Record<string, unknown>) => unknown;
	ruleX: (data: unknown[] | Record<string, unknown>) => unknown;
	frame: (opts?: Record<string, unknown>) => unknown;
	tip: (opts: Record<string, unknown>) => unknown;
	groupX: (
		reducers: Record<string, string>,
		opts: Record<string, unknown>,
	) => Record<string, unknown>;
}

let plotPromise: Promise<PlotApi | null> | null = null;

/** Lazy-load d3 and Plot in sequence; shared across all callers. */
export function loadPlot(): Promise<PlotApi | null> {
	if (plotPromise) return plotPromise;
	plotPromise = (async () => {
		const win = window as typeof window & { d3?: unknown; Plot?: PlotApi };
		await loadCdnScript<unknown>(D3_URL, () => win.d3);
		if (!win.d3) return null;
		const plot = await loadCdnScript<PlotApi>(PLOT_URL, () => win.Plot);
		return plot;
	})();
	return plotPromise;
}
