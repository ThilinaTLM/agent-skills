import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-toc";
export const spec: TagSpec = {
	optional: ["levels", "title"],
	customChildren: ["rd-chapter"],
};

export const chapterTagName = "rd-chapter";
export const chapterSpec: TagSpec = {
	optional: ["href"],
	allowedParents: ["rd-toc", "rd-chapter"],
	customChildren: ["rd-chapter"],
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = {
	tagName,
	spec,
	childTags: [{ tagName: chapterTagName, spec: chapterSpec }],
};
