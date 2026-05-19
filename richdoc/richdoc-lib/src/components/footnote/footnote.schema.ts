import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-footnote";
export const spec: TagSpec = {
	optional: ["mark"],
	customChildren: "any",
};
