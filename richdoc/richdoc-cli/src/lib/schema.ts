/**
 * Schema for richdoc custom elements.
 *
 * Loaded from `../../../assets/schema.json` (relative to this file), which is
 * produced by `build.ts` from the per-component `*.schema.ts` sources. The
 * CLI never hand-maintains the vocabulary — single source of truth.
 */

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export interface TagSpec {
	required?: readonly string[];
	optional?: readonly string[];
	customChildren?: readonly string[] | "any";
	allowedParents?: readonly string[];
	enums?: Readonly<Record<string, readonly string[]>>;
}

interface SchemaFile {
	$schema?: string;
	generated?: string;
	tags: Record<string, TagSpec>;
}

const SCHEMA_PATH = resolve(
	dirname(fileURLToPath(import.meta.url)),
	"..",
	"..",
	"..",
	"assets",
	"schema.json",
);

function loadSchema(): SchemaFile {
	try {
		const text = readFileSync(SCHEMA_PATH, "utf8");
		const parsed = JSON.parse(text) as SchemaFile;
		if (!parsed || typeof parsed !== "object" || !parsed.tags) {
			throw new Error("schema.json missing 'tags' object");
		}
		return parsed;
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err);
		throw new Error(
			`Could not load richdoc schema from ${SCHEMA_PATH}: ${msg}. Run \`richdoc build\` (or \`bun run build\` from the richdoc root) to generate it.`,
		);
	}
}

const SCHEMA_FILE = loadSchema();

export const SCHEMA: Readonly<Record<string, TagSpec>> = SCHEMA_FILE.tags;
export const ALLOWED_TAGS: readonly string[] = Object.keys(SCHEMA);
export const SCHEMA_GENERATED_AT: string | undefined = SCHEMA_FILE.generated;
export const SCHEMA_FILE_PATH = SCHEMA_PATH;

/** True if `tag` starts with `rd-`. */
export function isRdTag(tag: string): boolean {
	return tag.toLowerCase().startsWith("rd-");
}
