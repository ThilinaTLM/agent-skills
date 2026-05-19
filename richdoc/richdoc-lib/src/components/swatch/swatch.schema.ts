import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-swatch";
export const spec: TagSpec = {
	required: ["kind", "name", "value"],
	optional: ["note"],
	enums: {
		kind: ["color", "type", "space", "radius", "shadow"],
	},
};
