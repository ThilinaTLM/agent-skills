import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-rubric";
export const spec: TagSpec = {
	required: ["options"],
	optional: ["scale", "title"],
	customChildren: ["rd-criterion"],
};

export const criterionTagName = "rd-criterion";
export const criterionSpec: TagSpec = {
	required: ["label"],
	optional: ["weight"],
	allowedParents: ["rd-rubric"],
	customChildren: ["rd-score"],
};

export const scoreTagName = "rd-score";
export const scoreSpec: TagSpec = {
	required: ["value"],
	optional: ["note"],
	allowedParents: ["rd-criterion"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [
		{ tagName: criterionTagName, spec: criterionSpec },
		{ tagName: scoreTagName, spec: scoreSpec },
	],
};
