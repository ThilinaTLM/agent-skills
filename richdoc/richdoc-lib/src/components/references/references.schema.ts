import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-references";
export const spec: TagSpec = {
	optional: ["title"],
};

export const refTagName = "rd-ref";
export const refSpec: TagSpec = {
	required: ["key"],
	optional: ["author", "title", "url", "date", "publisher"],
	customChildren: "any",
};

export const citeTagName = "rd-cite";
export const citeSpec: TagSpec = {
	required: ["key"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [
		{ tagName: refTagName, spec: refSpec },
		{ tagName: citeTagName, spec: citeSpec },
	],
};
