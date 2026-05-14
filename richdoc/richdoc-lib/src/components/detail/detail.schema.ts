import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-detail";
export const spec: TagSpec = {
	required: ["summary"],
	optional: ["variant", "open"],
	customChildren: "any",
	enums: {
		variant: ["panel", "hairline", "question", "reveal"],
	},
};
