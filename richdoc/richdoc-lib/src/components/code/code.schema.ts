import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-code";
export const spec: TagSpec = {
	optional: ["lang", "title", "line-numbers", "highlight", "start"],
	customChildren: "any",
};
