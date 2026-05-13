import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-cols";
export const spec: TagSpec = {
	required: ["n"],
	customChildren: "any",
	enums: { n: ["2", "3", "4"] },
};
