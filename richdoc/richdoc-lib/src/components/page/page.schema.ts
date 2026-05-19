import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-page";
export const spec: TagSpec = {
	optional: ["theme", "mode", "width", "prefs"],
	customChildren: "any",
	enums: {
		// Extend this list when adding a theme — see AUTHORING.md.
		theme: ["editorial-warm", "graphite-modern"],
		mode: ["light", "dark", "auto"],
		// Reader-selectable page width. Default is "standard" (1280px).
		// The <rd-prefs> picker swaps this at runtime and persists in
		// localStorage.
		width: ["narrow", "standard", "wide", "full"],
		// Author opt-out for the floating preview picker. Default is
		// picker-on; set `prefs="off"` to suppress.
		prefs: ["off"],
	},
};
