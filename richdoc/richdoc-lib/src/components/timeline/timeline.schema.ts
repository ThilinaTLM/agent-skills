import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-timeline";
export const spec: TagSpec = {
	customChildren: ["rd-event"],
};

export const eventTagName = "rd-event";
export const eventSpec: TagSpec = {
	required: ["date"],
	optional: ["title"],
	allowedParents: ["rd-timeline"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [{ tagName: eventTagName, spec: eventSpec }],
};
