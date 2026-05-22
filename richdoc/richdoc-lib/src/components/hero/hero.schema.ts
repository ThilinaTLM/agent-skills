import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-hero";
export const spec: TagSpec = {
	required: ["title"],
	optional: ["eyebrow", "lede", "meta"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
