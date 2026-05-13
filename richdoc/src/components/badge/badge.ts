import { define } from "../../lib/base.ts";
import { spec, tagName } from "./badge.schema.ts";

class RdBadge extends HTMLElement {
	// Pure CSS; no upgrade required.
}

export function register(): void {
	define(tagName, RdBadge);
}
export { spec, tagName };
