import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-tabs";
export const spec: TagSpec = {
	customChildren: ["rd-tab"],
};

export const tabTagName = "rd-tab";
export const tabSpec: TagSpec = {
	required: ["label"],
	optional: ["active"],
	allowedParents: ["rd-tabs"],
	customChildren: "any",
};
