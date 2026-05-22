import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-page";
export const spec: TagSpec = {
	optional: ["theme", "mode", "width", "toc", "prefs", "diagram-endpoint"],
	customChildren: "any",
	enums: {
		// Extend this list when adding a theme — see AUTHORING.md.
		theme: ["editorial-warm", "graphite-modern"],
		mode: ["light", "dark", "auto"],
		// Reader-selectable page width. Default is "standard" (1280px).
		// The <rd-prefs> picker swaps this at runtime and persists in
		// localStorage.
		width: ["narrow", "standard", "wide", "full"],
		// Reader-selectable TOC position. Default is "auto" (right rail on
		// wide viewports, top bar otherwise). The <rd-prefs> picker swaps
		// this at runtime and persists in localStorage.
		toc: ["auto", "right", "left", "top"],
		// Author opt-out for the floating preview picker. Default is
		// picker-on; set `prefs="off"` to suppress.
		prefs: ["off"],
	},
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
