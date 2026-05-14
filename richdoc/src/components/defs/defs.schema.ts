import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-defs";
export const spec: TagSpec = {
	optional: ["title"],
	customChildren: ["rd-def"],
};

export const defTagName = "rd-def";
export const defSpec: TagSpec = {
	required: ["term"],
	allowedParents: ["rd-defs"],
	customChildren: "any",
};
