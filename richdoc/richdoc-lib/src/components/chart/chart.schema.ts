import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-chart";
export const spec: TagSpec = {
	required: ["kind"],
	optional: [
		"data",
		"format",
		"x",
		"y",
		"series",
		"labels",
		"title",
		"caption",
		"height",
		"legend",
	],
	enums: {
		kind: ["bar", "line", "area", "donut", "scatter", "heatmap"],
		format: ["json", "csv"],
	},
};
