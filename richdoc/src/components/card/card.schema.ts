import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-card";
export const spec: TagSpec = {
	optional: ["title", "accent"],
	customChildren: "any",
	enums: {
		accent: ["info", "success", "warn", "danger", "muted"],
	},
};
