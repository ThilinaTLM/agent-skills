import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-tabs";
export const spec: TagSpec = {
	customChildren: ["rd-tab"],
};

export const tabTagName = "rd-tab";
export const tabSpec: TagSpec = {
	required: ["label"],
	optional: ["active"],
	allowedParents: ["rd-tabs"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [{ tagName: tabTagName, spec: tabSpec }],
};
