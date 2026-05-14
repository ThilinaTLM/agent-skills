import { LUCIDE_NAMES } from "../../lib/lucide-names.generated.ts";
import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-icon";
export const spec: TagSpec = {
	required: ["name"],
	optional: ["size", "label"],
	enums: {
		// Full Lucide vocabulary at the pinned `lucide-static` version.
		// Inlined icons render synchronously; everything else is lazily
		// fetched from jsDelivr at runtime (see `lib/icon-loader.ts`).
		name: LUCIDE_NAMES as unknown as readonly string[],
		size: ["sm", "md", "lg"],
	},
};
