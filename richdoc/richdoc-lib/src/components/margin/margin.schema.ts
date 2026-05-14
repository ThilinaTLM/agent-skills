import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-margin";
export const spec: TagSpec = {
	optional: ["side"],
	customChildren: "any",
	enums: { side: ["right", "left"] },
};
