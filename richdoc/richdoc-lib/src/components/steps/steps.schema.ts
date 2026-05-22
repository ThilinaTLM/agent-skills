import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-steps";
export const spec: TagSpec = {
	customChildren: ["rd-step"],
};

export const stepTagName = "rd-step";
export const stepSpec: TagSpec = {
	required: ["title"],
	optional: ["done"],
	allowedParents: ["rd-steps"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [{ tagName: stepTagName, spec: stepSpec }],
};
