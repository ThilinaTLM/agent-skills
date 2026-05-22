import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-pros-cons";
export const spec: TagSpec = {
	optional: ["pros-title", "cons-title"],
	customChildren: ["rd-pro", "rd-con"],
};

export const proTagName = "rd-pro";
export const proSpec: TagSpec = {
	allowedParents: ["rd-pros-cons"],
	customChildren: "any",
};

export const conTagName = "rd-con";
export const conSpec: TagSpec = {
	allowedParents: ["rd-pros-cons"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [
		{ tagName: proTagName, spec: proSpec },
		{ tagName: conTagName, spec: conSpec },
	],
};
