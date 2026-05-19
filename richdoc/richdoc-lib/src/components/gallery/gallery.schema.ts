import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-gallery";
export const spec: TagSpec = {
	optional: ["cols", "title"],
	customChildren: ["rd-shot"],
	enums: { cols: ["2", "3", "4"] },
};

export const shotTagName = "rd-shot";
export const shotSpec: TagSpec = {
	required: ["src", "alt"],
	optional: ["caption", "width", "height"],
	allowedParents: ["rd-gallery"],
};
