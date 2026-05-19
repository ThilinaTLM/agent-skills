import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-compare";
export const spec: TagSpec = {
	required: ["headers"],
	customChildren: ["rd-row-cells"],
};

export const rowCellsTagName = "rd-row-cells";
export const rowCellsSpec: TagSpec = {
	required: ["label"],
	allowedParents: ["rd-compare"],
	customChildren: ["rd-cell"],
};

export const cellTagName = "rd-cell";
export const cellSpec: TagSpec = {
	optional: ["tone"],
	allowedParents: ["rd-row-cells"],
	customChildren: "any",
	enums: { tone: ["positive", "negative", "neutral"] },
};
