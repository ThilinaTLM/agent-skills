import { ICON_NAMES } from "../../lib/icons.ts";
import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-icon";
export const spec: TagSpec = {
	required: ["name"],
	optional: ["size", "label"],
	enums: {
		name: ICON_NAMES as readonly string[],
		size: ["sm", "md", "lg"],
	},
};
