import type { TagSpec } from "../../lib/types.ts";

// rd-kv ships with rd-row. rd-row's parent is restricted to rd-kv so it
// can't collide with rd-compare's rd-row-cells / rd-cell pair.

export const tagName = "rd-kv";
export const spec: TagSpec = {
	optional: ["title", "layout"],
	customChildren: ["rd-row"],
	enums: {
		layout: ["inline", "stacked"],
	},
};

export const rowTagName = "rd-row";
export const rowSpec: TagSpec = {
	required: ["key"],
	allowedParents: ["rd-kv"],
	customChildren: "any",
};
