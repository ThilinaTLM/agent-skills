import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-chart";
export const spec: TagSpec = {
	optional: [
		"variant",
		"kind",
		"data",
		"format",
		"x",
		"y",
		"series",
		"labels",
		"title",
		"caption",
		"height",
		"width",
		"legend",
		"color",
		"endpoint",
	],
	enums: {
		variant: ["chart", "sparkline"],
		kind: ["bar", "line", "area", "donut", "scatter", "heatmap"],
		format: ["json", "csv"],
	},
};
