import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-faq";
export const spec: TagSpec = {
	optional: ["title"],
	customChildren: ["rd-q"],
};

export const qTagName = "rd-q";
export const qSpec: TagSpec = {
	required: ["question"],
	optional: ["open"],
	allowedParents: ["rd-faq"],
	customChildren: ["rd-a"],
};

export const aTagName = "rd-a";
export const aSpec: TagSpec = {
	allowedParents: ["rd-q"],
	customChildren: "any",
};
