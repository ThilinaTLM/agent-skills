import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-quote";
export const spec: TagSpec = {
	optional: ["author", "cite", "source-url"],
	customChildren: "any",
};
