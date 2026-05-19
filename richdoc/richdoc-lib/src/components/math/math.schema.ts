import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-math";
export const spec: TagSpec = {
	optional: ["display"],
	enums: { display: ["block", "inline"] },
};
