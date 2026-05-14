import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-callout";
export const spec: TagSpec = {
	required: ["type"],
	optional: ["title"],
	customChildren: "any",
	enums: {
		type: ["info", "success", "warn", "danger", "note"],
	},
};
