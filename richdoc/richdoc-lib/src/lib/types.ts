/**
 * Shared type definitions for richdoc component schemas.
 * Each component exports a `spec: TagSpec` next to its implementation;
 * `build.ts` aggregates them into `assets/schema.json` for the CLI linter.
 */

export interface TagSpec {
	/** Attributes that must be present and non-empty. */
	required?: readonly string[];
	/** Recognized attributes beyond the required set. */
	optional?: readonly string[];
	/**
	 * Allowed rd-* children. Plain HTML children are always permitted.
	 * Use the literal "any" to mean: any rd-* child is allowed.
	 */
	customChildren?: readonly string[] | "any";
	/** This tag is only valid as a direct child of these parent tags. */
	allowedParents?: readonly string[];
	/** Enum constraints for specific attributes. */
	enums?: Readonly<Record<string, readonly string[]>>;
}

/** One tag in the vocabulary, paired with its spec. Used for parent
 * tags, their declarative children, and anywhere the rd-* vocabulary
 * is iterated as data (schema-registry, `richdoc components`). */
export interface TagEntry {
	readonly tagName: string;
	readonly spec: TagSpec;
}

/** Each component's `.schema.ts` exports a `bundle: SchemaBundle`
 * declaring the parent tag and (when applicable) its child tags in
 * one place. `schema-registry.ts` flat-maps every bundle into a
 * single ordered list of `TagEntry`s.
 *
 * Child tags don't carry their own `register()` because the parent's
 * `register()` (in the matching `.ts` file) handles every custom
 * element definition for the bundle. */
export interface SchemaBundle {
	readonly tagName: string;
	readonly spec: TagSpec;
	readonly childTags?: readonly TagEntry[];
}

/** A registerable component: parent schema + the `register()` call
 * that defines every custom element it needs (parent + children).
 * Currently only consumed inside the runtime `registry.ts`. */
export interface ComponentModule extends TagEntry {
	register(): void;
}
