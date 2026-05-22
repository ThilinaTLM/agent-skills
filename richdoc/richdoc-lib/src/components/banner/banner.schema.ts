import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-banner";
export const spec: TagSpec = {
	required: ["type"],
	optional: ["message"],
	customChildren: "any",
	enums: {
		type: ["draft", "frozen", "archived", "confidential", "info"],
	},
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
