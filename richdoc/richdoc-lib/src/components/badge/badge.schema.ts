import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-badge";
export const spec: TagSpec = {
	optional: ["variant"],
	customChildren: "any",
	enums: {
		variant: ["info", "success", "warn", "danger", "muted"],
	},
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
