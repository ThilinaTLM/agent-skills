import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-hero";
export const spec: TagSpec = {
	required: ["title"],
	optional: ["eyebrow", "lede", "meta"],
	customChildren: "any",
};
