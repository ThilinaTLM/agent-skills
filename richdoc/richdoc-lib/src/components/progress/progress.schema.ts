import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-progress";
export const spec: TagSpec = {
	required: ["value"],
	optional: ["label", "tone"],
	enums: { tone: ["positive", "negative", "neutral"] },
};
