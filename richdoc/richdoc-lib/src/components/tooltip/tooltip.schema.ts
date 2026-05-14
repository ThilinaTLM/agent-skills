import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-tooltip";
export const spec: TagSpec = {
	required: ["term"],
	optional: ["placement"],
	customChildren: "any",
	enums: { placement: ["auto", "top", "bottom"] },
};
