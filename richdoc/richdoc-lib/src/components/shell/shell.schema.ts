import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-shell";
export const spec: TagSpec = {
	optional: ["title"],
	customChildren: ["rd-prompt", "rd-output"],
};

export const promptTagName = "rd-prompt";
export const promptSpec: TagSpec = {
	optional: ["cwd", "user"],
	allowedParents: ["rd-shell"],
	customChildren: "any",
};

export const outputTagName = "rd-output";
export const outputSpec: TagSpec = {
	optional: ["tone"],
	allowedParents: ["rd-shell"],
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
		{ tagName: promptTagName, spec: promptSpec },
		{ tagName: outputTagName, spec: outputSpec },
	],
};
