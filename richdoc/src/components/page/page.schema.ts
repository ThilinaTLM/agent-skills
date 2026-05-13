import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-page";
export const spec: TagSpec = {
	optional: ["theme"],
	customChildren: "any",
	enums: { theme: ["light", "dark", "auto"] },
};
