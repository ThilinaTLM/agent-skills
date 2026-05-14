import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-sidenote";
export const spec: TagSpec = {
	optional: ["mark"],
	customChildren: "any",
};
