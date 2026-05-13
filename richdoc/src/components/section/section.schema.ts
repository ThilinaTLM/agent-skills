import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-section";
export const spec: TagSpec = {
	optional: ["title", "id"],
	customChildren: "any",
};
