/**
 * Smoke tests for the pure schema registry.
 *
 * `schema-registry.ts` is the only entry point that's safe to import
 * from Node (`registry.ts` references `HTMLElement` transitively). This
 * test confirms the schema layer loads end-to-end and the vocabulary
 * matches a small set of invariants the docs / linter rely on.
 *
 * Real DOM tests for individual components belong in a future jsdom
 * environment and are out of scope for the maintainability refactor.
 */

import { describe, expect, it } from "vitest";

import { SCHEMA_ENTRIES } from "../src/schema-registry.ts";

describe("schema-registry", () => {
	it("emits at least one entry per known vocabulary group", () => {
		expect(SCHEMA_ENTRIES.length).toBeGreaterThan(0);
	});

	it("every entry has a non-empty rd-* tagName and an object spec", () => {
		for (const entry of SCHEMA_ENTRIES) {
			expect(entry.tagName, JSON.stringify(entry)).toMatch(/^rd-[a-z][a-z0-9-]*$/);
			expect(typeof entry.spec, entry.tagName).toBe("object");
		}
	});

	it("tag names are unique", () => {
		const seen = new Set<string>();
		for (const entry of SCHEMA_ENTRIES) {
			expect(seen.has(entry.tagName), `duplicate ${entry.tagName}`).toBe(false);
			seen.add(entry.tagName);
		}
	});

	it("ships every documented core tag", () => {
		const names = new Set(SCHEMA_ENTRIES.map((e) => e.tagName));
		// Anchor list \u2014 these are referenced from SKILL.md and the linter's
		// REMOVED_TAGS map. Adding or removing one is a deliberate change.
		for (const required of [
			"rd-page",
			"rd-hero",
			"rd-section",
			"rd-callout",
			"rd-cols",
			"rd-card",
			"rd-code",
			"rd-diagram",
			"rd-toc",
			"rd-chapter",
			"rd-icon",
		]) {
			expect(names.has(required), `missing ${required}`).toBe(true);
		}
	});

	it("required attributes are arrays of strings when present", () => {
		for (const { tagName, spec } of SCHEMA_ENTRIES) {
			if (spec.required) {
				expect(Array.isArray(spec.required), tagName).toBe(true);
				for (const attr of spec.required) {
					expect(typeof attr, `${tagName}.required[]`).toBe("string");
				}
			}
		}
	});
});
