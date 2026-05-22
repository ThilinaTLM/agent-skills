import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
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

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
