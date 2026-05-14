import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-sparkline";
export const spec: TagSpec = {
	required: ["values"],
	optional: ["kind", "width", "height", "color", "endpoint"],
	enums: { kind: ["line", "bar", "area"] },
};
