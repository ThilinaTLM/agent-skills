import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-roadmap";
export const spec: TagSpec = {
	required: ["start", "end"],
	optional: ["unit", "title"],
	customChildren: ["rd-lane"],
	enums: { unit: ["day", "week", "month", "quarter"] },
};

export const laneTagName = "rd-lane";
export const laneSpec: TagSpec = {
	required: ["name"],
	allowedParents: ["rd-roadmap"],
	customChildren: ["rd-item"],
};

export const itemTagName = "rd-item";
export const itemSpec: TagSpec = {
	required: ["start", "end", "label"],
	optional: ["tone", "progress"],
	allowedParents: ["rd-lane"],
	customChildren: "any",
	enums: { tone: ["positive", "negative", "neutral"] },
};
