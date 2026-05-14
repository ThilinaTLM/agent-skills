import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-page";
export const spec: TagSpec = {
	optional: ["theme", "mode"],
	customChildren: "any",
	enums: {
		// Extend this list when adding a theme — see AUTHORING.md.
		theme: ["editorial-warm"],
		mode: ["light", "dark", "auto"],
	},
};
