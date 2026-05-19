import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-pros-cons";
export const spec: TagSpec = {
	optional: ["pros-title", "cons-title"],
	customChildren: ["rd-pro", "rd-con"],
};

export const proTagName = "rd-pro";
export const proSpec: TagSpec = {
	allowedParents: ["rd-pros-cons"],
	customChildren: "any",
};

export const conTagName = "rd-con";
export const conSpec: TagSpec = {
	allowedParents: ["rd-pros-cons"],
	customChildren: "any",
};
