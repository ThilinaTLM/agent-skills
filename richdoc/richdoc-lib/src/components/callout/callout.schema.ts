import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-callout";
export const spec: TagSpec = {
	required: ["type"],
	optional: ["title"],
	customChildren: "any",
	enums: {
		type: ["info", "success", "warn", "danger", "note", "tldr"],
	},
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
