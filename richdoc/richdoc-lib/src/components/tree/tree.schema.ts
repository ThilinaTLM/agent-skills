import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-tree";
export const spec: TagSpec = {
	optional: ["title"],
	customChildren: ["rd-node"],
};

export const nodeTagName = "rd-node";
export const nodeSpec: TagSpec = {
	required: ["label"],
	optional: ["open", "icon"],
	allowedParents: ["rd-tree", "rd-node"],
	customChildren: ["rd-node"],
};
