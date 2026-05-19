import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-plantuml";
export const spec: TagSpec = {
	optional: ["endpoint", "theme"],
	customChildren: "any",
};
