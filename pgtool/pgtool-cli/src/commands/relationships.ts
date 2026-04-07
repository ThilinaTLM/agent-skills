import { defineCommand } from "citty";
import { getDefaultSchema } from "../lib/config";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatTable, outputJson } from "../lib/output";
import type { RelationshipInfo, RelationshipsResult } from "../types";

export const relationshipsCommand = defineCommand({
	meta: {
		name: "relationships",
		description: "List all foreign key relationships in a schema",
	},
	args: {
		schema: {
			type: "positional",
			description: "Schema name (default: from config or 'public')",
			required: false,
		},
		root: {
			type: "string",
			alias: "r",
			description: "Project root directory",
		},
		plain: {
			type: "boolean",
			description: "Human-readable output instead of JSON",
		},
	},
	async run({ args }) {
		const plain = args.plain ?? false;
		const { config } = initPgTool(args.root, plain);
		registerCleanup();

		const schema = args.schema || getDefaultSchema(config);

		const result = await query<{
			constraint_name: string;
			from_schema: string;
			from_table: string;
			from_columns: string;
			to_schema: string;
			to_table: string;
			to_columns: string;
		}>(
			`
      SELECT
        c.conname AS constraint_name,
        ns.nspname AS from_schema,
        t.relname AS from_table,
        array_to_string(array_agg(DISTINCT a.attname ORDER BY a.attname), ', ') AS from_columns,
        nsr.nspname AS to_schema,
        r.relname AS to_table,
        array_to_string(array_agg(DISTINCT ar.attname ORDER BY ar.attname), ', ') AS to_columns
      FROM pg_catalog.pg_constraint c
      JOIN pg_catalog.pg_class t ON t.oid = c.conrelid
      JOIN pg_catalog.pg_namespace ns ON ns.oid = t.relnamespace
      JOIN pg_catalog.pg_class r ON r.oid = c.confrelid
      JOIN pg_catalog.pg_namespace nsr ON nsr.oid = r.relnamespace
      JOIN pg_catalog.pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
      JOIN pg_catalog.pg_attribute ar ON ar.attrelid = r.oid AND ar.attnum = ANY(c.confkey)
      WHERE c.contype = 'f'
        AND (ns.nspname = $1 OR nsr.nspname = $1)
      GROUP BY c.conname, ns.nspname, t.relname, nsr.nspname, r.relname
      ORDER BY ns.nspname, t.relname, c.conname
    `,
			[schema],
		);

		if (!result.ok) {
			handleError(result, plain);
		}

		const relationships: RelationshipInfo[] = result.result.rows.map((row) => ({
			constraintName: row.constraint_name,
			fromSchema: row.from_schema,
			fromTable: row.from_table,
			fromColumns: row.from_columns.split(", "),
			toSchema: row.to_schema,
			toTable: row.to_table,
			toColumns: row.to_columns.split(", "),
		}));

		const response: { ok: true } & RelationshipsResult = {
			ok: true,
			relationships,
		};

		if (plain) {
			console.log(`Foreign key relationships in/to schema '${schema}':\n`);
			if (relationships.length === 0) {
				console.log("No relationships found");
			} else {
				console.log(
					formatTable(
						["From", "Columns", "To", "Columns"],
						relationships.map((r) => [
							`${r.fromSchema}.${r.fromTable}`,
							r.fromColumns.join(", "),
							`${r.toSchema}.${r.toTable}`,
							r.toColumns.join(", "),
						]),
					),
				);
			}
			process.exit(0);
		}

		outputJson(response);
	},
});
