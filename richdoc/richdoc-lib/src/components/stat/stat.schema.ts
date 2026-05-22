import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-stat";
export const spec: TagSpec = {
	required: ["value"],
	optional: ["label", "trend", "delta", "tone"],
	enums: {
		trend: ["up", "down", "flat"],
		tone: ["positive", "negative", "neutral"],
	},
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
