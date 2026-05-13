import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-detail";
export const spec: TagSpec = {
	required: ["summary"],
	optional: ["open"],
	customChildren: "any",
};
