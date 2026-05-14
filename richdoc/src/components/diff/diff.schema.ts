import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-diff";
export const spec: TagSpec = {
	optional: ["lang", "title", "line-numbers"],
};
