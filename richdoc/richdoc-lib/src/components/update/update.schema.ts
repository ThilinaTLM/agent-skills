import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-update";
export const spec: TagSpec = {
	required: ["date"],
	optional: ["author", "kind", "title"],
	customChildren: "any",
	enums: { kind: ["release", "change", "note"] },
};
