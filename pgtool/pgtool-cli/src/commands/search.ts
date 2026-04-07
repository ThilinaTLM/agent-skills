import { defineCommand } from "citty";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatTable, outputJson } from "../lib/output";
import type { SearchResult } from "../types";

export const searchCommand = defineCommand({
	meta: {
		name: "search",
		description: "Search for tables and columns matching a pattern",
	},
	args: {
		pattern: {
			type: "positional",
			description: "Search pattern (case-insensitive)",
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
		initPgTool(args.root, plain);
		registerCleanup();

		const pattern = `%${args.pattern}%`;

		// Search for matching tables
		const tablesResult = await query<{
			schema_name: string;
			table_name: string;
		}>(
			`
      SELECT
        n.nspname AS schema_name,
        c.relname AS table_name
      FROM pg_catalog.pg_class c
      LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind IN ('r', 'v', 'm', 'f')
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND c.relname ILIKE $1
      ORDER BY n.nspname, c.relname
      `,
			[pattern],
		);

		if (!tablesResult.ok) {
			handleError(tablesResult, plain);
		}

		// Search for matching columns
		const columnsResult = await query<{
			schema_name: string;
			table_name: string;
			column_name: string;
			data_type: string;
		}>(
			`
      SELECT
        n.nspname AS schema_name,
        c.relname AS table_name,
        a.attname AS column_name,
        pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type
      FROM pg_catalog.pg_attribute a
      JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind IN ('r', 'v', 'm', 'f')
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND a.attnum > 0
        AND NOT a.attisdropped
        AND a.attname ILIKE $1
      ORDER BY n.nspname, c.relname, a.attnum
      `,
			[pattern],
		);

		if (!columnsResult.ok) {
			handleError(columnsResult, plain);
		}

		const tables = tablesResult.result.rows.map((row) => ({
			schema: row.schema_name,
			name: row.table_name,
		}));

		const columns = columnsResult.result.rows.map((row) => ({
			schema: row.schema_name,
			table: row.table_name,
			column: row.column_name,
			type: row.data_type,
		}));

		const response: { ok: true } & SearchResult = {
			ok: true,
			pattern: args.pattern,
			matches: {
				tables,
				columns,
			},
		};

		if (plain) {
			console.log(`Search results for '${args.pattern}':\n`);

			if (tables.length > 0) {
				console.log(`Tables (${tables.length}):`);
				console.log(
					formatTable(
						["Schema", "Table"],
						tables.map((t) => [t.schema, t.name]),
					),
				);
				console.log();
			} else {
				console.log("No matching tables found\n");
			}

			if (columns.length > 0) {
				console.log(`Columns (${columns.length}):`);
				console.log(
					formatTable(
						["Schema", "Table", "Column", "Type"],
						columns.map((c) => [c.schema, c.table, c.column, c.type]),
					),
				);
			} else {
				console.log("No matching columns found");
			}

			process.exit(0);
		}

		outputJson(response);
	},
});
