import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-toc";
export const spec: TagSpec = {
	optional: ["levels", "title"],
};
