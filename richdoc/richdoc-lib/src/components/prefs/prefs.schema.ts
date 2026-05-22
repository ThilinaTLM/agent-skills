import type { SchemaBundle, TagSpec } from "../../lib/types.ts";
export const tagName = "rd-prefs";

/**
 * `<rd-prefs>` is JS-injected by `<rd-page>` (unless suppressed with
 * `<rd-page prefs="off">`). Authors are not expected to write it, but
 * the schema entry exists so lint passes if someone copies it into
 * source and so component introspection lists it.
 */
export const spec: TagSpec = {
	// No rd-* children allowed (rd-prefs is JS-injected and self-contained).
	// The previous `"none"` value was outside the TagSpec union and got
	// silently dropped by the linter; an empty array enforces the intent.
	customChildren: [],
};

// Registry bundle consumed by `schema-registry.ts`. Lists the parent
// tag and every child tag in one declarative record so adding or
// removing a child only touches this file.
export const bundle: SchemaBundle = { tagName, spec };
