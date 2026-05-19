import type { TagSpec } from "../../lib/types.ts";

export const tagName = "rd-prefs";

/**
 * `<rd-prefs>` is JS-injected by `<rd-page>` (unless suppressed with
 * `<rd-page prefs="off">`). Authors are not expected to write it, but
 * the schema entry exists so lint passes if someone copies it into
 * source and so component introspection lists it.
 */
export const spec: TagSpec = {
	customChildren: "none",
};
