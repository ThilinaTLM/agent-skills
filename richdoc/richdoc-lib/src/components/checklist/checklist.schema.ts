import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-checklist";
export const spec: TagSpec = {
	customChildren: ["rd-task"],
};

export const taskTagName = "rd-task";
export const taskSpec: TagSpec = {
	optional: ["done", "assignee", "due"],
	allowedParents: ["rd-checklist"],
	customChildren: "any",
};
