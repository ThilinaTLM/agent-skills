import { defineCommand } from "citty";
import { getDefaultSchema } from "../lib/config";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatBytes, formatTable, outputJson } from "../lib/output";
import type { IndexInfo, IndexesResult } from "../types";

export const indexesCommand = defineCommand({
	meta: {
		name: "indexes",
		description: "List indexes on a table",
	},
	args: {
		table: {
			type: "positional",
			description: "Table name (can include schema prefix: schema.table)",
			required: true,
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

		// Parse table name
		let schema: string;
		let tableName: string;

		if (args.table.includes(".")) {
			const parts = args.table.split(".");
			schema = parts[0];
			tableName = parts.slice(1).join(".");
		} else {
			schema = getDefaultSchema(config);
			tableName = args.table;
		}

		const result = await query<{
			index_name: string;
			is_unique: boolean;
			is_primary: boolean;
			columns: string;
			index_type: string;
			size_bytes: string | null;
			definition: string;
		}>(
			`
      SELECT
        i.relname AS index_name,
        ix.indisunique AS is_unique,
        ix.indisprimary AS is_primary,
        array_to_string(array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)), ', ') AS columns,
        am.amname AS index_type,
        pg_relation_size(i.oid)::bigint AS size_bytes,
        pg_catalog.pg_get_indexdef(ix.indexrelid) AS definition
      FROM pg_catalog.pg_class t
      JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace
      JOIN pg_catalog.pg_index ix ON t.oid = ix.indrelid
      JOIN pg_catalog.pg_class i ON i.oid = ix.indexrelid
      JOIN pg_catalog.pg_am am ON am.oid = i.relam
      JOIN pg_catalog.pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
      WHERE n.nspname = $1 AND t.relname = $2
      GROUP BY i.relname, ix.indisunique, ix.indisprimary, am.amname, i.oid, ix.indexrelid
      ORDER BY i.relname
    `,
			[schema, tableName],
		);

		if (!result.ok) {
			handleError(result, plain);
		}

		const indexes: IndexInfo[] = result.result.rows.map((row) => ({
			name: row.index_name,
			unique: row.is_unique,
			primary: row.is_primary,
			columns: row.columns.split(", "),
			type: row.index_type,
			size: row.size_bytes ? formatBytes(Number(row.size_bytes)) : null,
			definition: row.definition,
		}));

		const response: { ok: true } & IndexesResult = {
			ok: true,
			schema,
			table: tableName,
			indexes,
		};

		if (plain) {
			console.log(`Indexes on ${schema}.${tableName}:\n`);
			if (indexes.length === 0) {
				console.log("No indexes found");
			} else {
				console.log(
					formatTable(
						["Name", "Unique", "Primary", "Type", "Columns", "Size"],
						indexes.map((idx) => [
							idx.name,
							idx.unique ? "YES" : "NO",
							idx.primary ? "YES" : "NO",
							idx.type,
							idx.columns.join(", "),
							idx.size ?? "N/A",
						]),
					),
				);
			}
			process.exit(0);
		}

		outputJson(response);
	},
});
