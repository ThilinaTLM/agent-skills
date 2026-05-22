import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-cols";
export const spec: TagSpec = {
	optional: ["n", "template"],
	customChildren: "any",
	enums: { n: ["2", "3", "4"] },
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
