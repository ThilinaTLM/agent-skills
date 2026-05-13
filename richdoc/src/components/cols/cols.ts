import { define } from "../../lib/base.ts";
import { spec, tagName } from "./cols.schema.ts";

class RdCols extends HTMLElement {
	// Pure CSS layout; no upgrade needed.
}

export function register(): void {
	define(tagName, RdCols);
}
export { spec, tagName };
