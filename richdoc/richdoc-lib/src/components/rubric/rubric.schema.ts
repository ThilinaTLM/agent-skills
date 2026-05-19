import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-rubric";
export const spec: TagSpec = {
	required: ["options"],
	optional: ["scale", "title"],
	customChildren: ["rd-criterion"],
};

export const criterionTagName = "rd-criterion";
export const criterionSpec: TagSpec = {
	required: ["label"],
	optional: ["weight"],
	allowedParents: ["rd-rubric"],
	customChildren: ["rd-score"],
};

export const scoreTagName = "rd-score";
export const scoreSpec: TagSpec = {
	required: ["value"],
	optional: ["note"],
	allowedParents: ["rd-criterion"],
	customChildren: "any",
};
