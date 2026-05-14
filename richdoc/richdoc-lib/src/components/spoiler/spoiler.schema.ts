import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-spoiler";
export const spec: TagSpec = {
	optional: ["label"],
	customChildren: "any",
};
