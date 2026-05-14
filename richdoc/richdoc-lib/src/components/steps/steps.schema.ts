import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-steps";
export const spec: TagSpec = {
	customChildren: ["rd-step"],
};

export const stepTagName = "rd-step";
export const stepSpec: TagSpec = {
	required: ["title"],
	optional: ["done"],
	allowedParents: ["rd-steps"],
	customChildren: "any",
};
