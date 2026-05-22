import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-detail";
export const spec: TagSpec = {
	required: ["summary"],
	optional: ["variant", "open"],
	customChildren: "any",
	enums: {
		variant: ["panel", "hairline", "question", "reveal"],
	},
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
