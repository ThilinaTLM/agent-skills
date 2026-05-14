import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-figure";
export const spec: TagSpec = {
	optional: ["caption"],
	customChildren: "any",
};
