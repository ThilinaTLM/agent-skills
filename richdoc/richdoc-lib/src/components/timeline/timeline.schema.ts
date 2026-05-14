import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-timeline";
export const spec: TagSpec = {
	customChildren: ["rd-event"],
};

export const eventTagName = "rd-event";
export const eventSpec: TagSpec = {
	required: ["date"],
	optional: ["title"],
	allowedParents: ["rd-timeline"],
	customChildren: "any",
};
