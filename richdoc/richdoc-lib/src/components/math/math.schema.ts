import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-math";
export const spec: TagSpec = {
	optional: ["display"],
	enums: { display: ["block", "inline"] },
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
