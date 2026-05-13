import { defineCommand } from "citty";
import { jsonOk } from "../lib/output.ts";
import {
	SCHEMA,
	SCHEMA_FILE_PATH,
	SCHEMA_GENERATED_AT,
	type TagSpec,
} from "../lib/schema.ts";

export const componentsCommand = defineCommand({
	meta: {
		name: "components",
		description:
			"List every richdoc tag with its allowed attributes and children.",
	},
	args: {
		plain: {
			type: "boolean",
			description: "Human-readable table output instead of JSON.",
			default: false,
		},
		tag: {
			type: "string",
			description: "Show only the spec for one tag (e.g. rd-stat).",
		},
	},
	async run({ args }) {
		const entries: [string, TagSpec][] = Object.entries(SCHEMA);
		const filtered = args.tag
			? entries.filter(([t]) => t === args.tag)
			: entries;

		if (args.plain) {
			printPlain(filtered);
			return;
		}

		jsonOk({
			schemaPath: SCHEMA_FILE_PATH,
			generated: SCHEMA_GENERATED_AT ?? null,
			count: filtered.length,
			tags: filtered.map(([tagName, spec]) => ({ tagName, ...spec })),
		});
	},
});

function printPlain(entries: [string, TagSpec][]): void {
	if (entries.length === 0) {
		console.log("(no matching tags)");
		return;
	}
	const rows: string[][] = [["TAG", "REQUIRED", "OPTIONAL", "CHILDREN"]];
	for (const [tag, spec] of entries) {
		const req = (spec.required ?? []).join(", ") || "—";
		const opt = (spec.optional ?? []).join(", ") || "—";
		const children = Array.isArray(spec.customChildren)
			? spec.customChildren.map((c) => `<${c}>`).join(", ")
			: spec.customChildren === "any"
				? "any rd-*"
				: "—";
		rows.push([`<${tag}>`, req, opt, children]);
	}

	const widths = rows[0].map((_, col) =>
		Math.max(...rows.map((r) => stripAnsi(r[col]).length)),
	);
	const fmt = (cells: string[]) =>
		cells.map((c, i) => c.padEnd(widths[i])).join("  ");

	console.log(fmt(rows[0]));
	console.log(widths.map((w) => "─".repeat(w)).join("  "));
	for (const r of rows.slice(1)) console.log(fmt(r));

	// Enums after the table.
	const withEnums = entries.filter(([, s]) => s.enums);
	if (withEnums.length > 0) {
		console.log("\nEnum constraints:");
		for (const [tag, spec] of withEnums) {
			for (const [attr, vals] of Object.entries(spec.enums ?? {})) {
				console.log(`  <${tag} ${attr}>  → ${vals.join(", ")}`);
			}
		}
	}
}

function stripAnsi(s: string): string {
	return s;
}
