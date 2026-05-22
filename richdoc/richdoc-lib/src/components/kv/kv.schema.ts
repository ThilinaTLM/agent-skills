import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
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

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [{ tagName: rowTagName, spec: rowSpec }],
};
