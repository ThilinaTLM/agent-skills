import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-code";
export const spec: TagSpec = {
	optional: ["lang", "title", "line-numbers", "highlight", "start"],
	customChildren: "any",
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
