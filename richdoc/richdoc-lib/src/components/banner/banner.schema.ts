import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-banner";
export const spec: TagSpec = {
	required: ["type"],
	optional: ["message"],
	customChildren: "any",
	enums: {
		type: ["draft", "frozen", "archived", "confidential", "info"],
	},
};
