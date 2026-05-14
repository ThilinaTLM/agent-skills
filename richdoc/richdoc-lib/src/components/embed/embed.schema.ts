import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-embed";
export const spec: TagSpec = {
	required: ["src", "title"],
	optional: ["aspect", "caption"],
};
