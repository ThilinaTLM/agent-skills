import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-badge";
export const spec: TagSpec = {
	optional: ["variant"],
	customChildren: "any",
	enums: {
		variant: ["info", "success", "warn", "danger", "muted"],
	},
};
