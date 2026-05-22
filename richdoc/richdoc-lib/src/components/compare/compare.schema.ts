import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-compare";
export const spec: TagSpec = {
	required: ["headers"],
	customChildren: ["rd-row-cells"],
};

export const rowCellsTagName = "rd-row-cells";
export const rowCellsSpec: TagSpec = {
	required: ["label"],
	allowedParents: ["rd-compare"],
	customChildren: ["rd-cell"],
};

export const cellTagName = "rd-cell";
export const cellSpec: TagSpec = {
	optional: ["tone"],
	allowedParents: ["rd-row-cells"],
	customChildren: "any",
	enums: { tone: ["positive", "negative", "neutral"] },
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [
		{ tagName: rowCellsTagName, spec: rowCellsSpec },
		{ tagName: cellTagName, spec: cellSpec },
	],
};
