import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-checklist";
export const spec: TagSpec = {
	customChildren: ["rd-task"],
};

export const taskTagName = "rd-task";
export const taskSpec: TagSpec = {
	optional: ["done", "assignee", "due"],
	allowedParents: ["rd-checklist"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [{ tagName: taskTagName, spec: taskSpec }],
};
