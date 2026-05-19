import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-references";
export const spec: TagSpec = {
	optional: ["title"],
};

export const refTagName = "rd-ref";
export const refSpec: TagSpec = {
	required: ["key"],
	optional: ["author", "title", "url", "date", "publisher"],
	customChildren: "any",
};

export const citeTagName = "rd-cite";
export const citeSpec: TagSpec = {
	required: ["key"],
	customChildren: "any",
};
