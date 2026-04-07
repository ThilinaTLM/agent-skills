import { defineCommand } from "citty";
import { getDefaultSchema } from "../lib/config";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatTable, outputJson } from "../lib/output";
import type { SampleResult } from "../types";

/**
 * Parse table identifier into schema and table name.
 * Supports formats: "table", "schema.table"
 */
function parseTableId(
	tableId: string,
	defaultSchema: string,
): { schema: string; table: string } {
	const parts = tableId.split(".");
	if (parts.length === 2) {
		return { schema: parts[0], table: parts[1] };
	}
	return { schema: defaultSchema, table: tableId };
}

export const sampleCommand = defineCommand({
	meta: {
		name: "sample",
		description: "Get sample rows from a table",
	},
	args: {
		table: {
			type: "positional",
			description: "Table name (or schema.table)",
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
		limit: {
			type: "string",
			alias: "l",
			description: "Number of rows to return (default: 5)",
		},
	},
	async run({ args }) {
		const plain = args.plain ?? false;
		const { config } = initPgTool(args.root, plain);
		registerCleanup();

		const limit = args.limit ? Number.parseInt(args.limit, 10) : 5;
		const { schema, table } = parseTableId(
			args.table,
			getDefaultSchema(config),
		);

		// Use quoted identifiers to handle special characters
		const sql = `SELECT * FROM "${schema}"."${table}" LIMIT ${limit}`;
		const result = await query(sql);

		if (!result.ok) {
			handleError(result, plain);
		}

		const columns = result.result.fields.map((f) => f.name);
		const response: { ok: true } & SampleResult = {
			ok: true,
			schema,
			table,
			rows: result.result.rows,
			rowCount: result.result.rowCount,
			columns,
		};

		if (plain) {
			console.log(
				`Sample from '${schema}.${table}' (${result.result.rowCount} rows):\n`,
			);
			if (result.result.rows.length === 0) {
				console.log("No rows found");
			} else {
				const rows = result.result.rows.map((row) =>
					columns.map((col) => {
						const value = row[col];
						if (value === null) return "NULL";
						if (typeof value === "object") return JSON.stringify(value);
						return String(value);
					}),
				);
				console.log(formatTable(columns, rows));
			}
			process.exit(0);
		}

		outputJson(response);
	},
});
