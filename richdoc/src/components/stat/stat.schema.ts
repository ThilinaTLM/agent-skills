import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-stat";
export const spec: TagSpec = {
	required: ["value"],
	optional: ["label", "trend", "delta", "tone"],
	enums: {
		trend: ["up", "down", "flat"],
		tone: ["positive", "negative", "neutral"],
	},
};
