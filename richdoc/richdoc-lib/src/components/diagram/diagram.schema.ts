import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-diagram";

/**
 * Supported diagram languages. Mirrors the Kroki-supported set (see the
 * `diagram` skill in this repo) and the enum used by `diagram-cli`. Keep
 * this list in sync with that CLI.
 */
export const DIAGRAM_LANGS = [
	"mermaid",
	"plantuml",
	"graphviz",
	"d2",
	"dbml",
	"bpmn",
	"c4plantuml",
	"erd",
	"ditaa",
	"excalidraw",
	"nomnoml",
	"pikchr",
	"structurizr",
	"svgbob",
	"tikz",
	"vega",
	"vegalite",
	"wavedrom",
	"wireviz",
	"bytefield",
	"blockdiag",
	"seqdiag",
	"actdiag",
	"nwdiag",
	"packetdiag",
	"rackdiag",
] as const;

export const spec: TagSpec = {
	required: ["lang"],
	optional: ["endpoint", "theme", "title", "caption"],
	customChildren: "any",
	enums: {
		lang: DIAGRAM_LANGS as unknown as string[],
	},
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
