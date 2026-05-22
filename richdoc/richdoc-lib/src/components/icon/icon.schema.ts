import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
import { LUCIDE_NAMES } from "./lucide-names.generated.ts";

export const tagName = "rd-icon";
export const spec: TagSpec = {
	required: ["name"],
	optional: ["size", "label"],
	enums: {
		// Full Lucide vocabulary at the pinned `lucide-static` version.
		// Inlined icons render synchronously; everything else is lazily
		// fetched from jsDelivr at runtime (see `./icon-loader.ts`).
		name: LUCIDE_NAMES as unknown as readonly string[],
		size: ["sm", "md", "lg"],
	},
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
