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

export interface ComponentModule {
	readonly tagName: string;
	readonly spec: TagSpec;
	register(): void;
}
