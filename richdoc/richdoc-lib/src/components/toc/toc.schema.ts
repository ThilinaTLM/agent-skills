import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-toc";
export const spec: TagSpec = {
	optional: ["levels", "title"],
	customChildren: ["rd-chapter"],
};

export const chapterTagName = "rd-chapter";
export const chapterSpec: TagSpec = {
	optional: ["href"],
	allowedParents: ["rd-toc", "rd-chapter"],
	customChildren: ["rd-chapter"],
};
