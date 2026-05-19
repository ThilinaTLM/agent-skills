import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-decision";
export const spec: TagSpec = {
	required: ["status"],
	optional: ["id", "date", "deciders", "title"],
	customChildren: "any",
	enums: {
		status: ["proposed", "accepted", "superseded", "rejected"],
	},
};
