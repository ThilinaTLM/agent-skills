import { defineCommand } from "citty";
import { globalArgs, initOptsFromArgs } from "../lib/args.ts";
import { getDefaultSchema } from "../lib/config.ts";
import { query } from "../lib/connection.ts";
import {
	handleError,
	initDaemonConnection,
	initPgTool,
	registerCleanup,
} from "../lib/init.ts";
import { outputJson } from "../lib/output.ts";
import type { CountResult } from "../types";

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

export const countCommand = defineCommand({
	meta: {
		name: "count",
		description: "Count rows in a table",
	},
	args: {
		table: {
			type: "positional",
			description: "Table name (or schema.table)",
			required: true,
		},
		...globalArgs,
	},
	async run({ args }) {
		const plain = args.plain ?? false;
		const { config } = initPgTool(initOptsFromArgs(args));
		registerCleanup();
		await initDaemonConnection();

		const { schema, table } = parseTableId(
			args.table,
			getDefaultSchema(config),
		);

		// Use quoted identifiers to handle special characters
		const sql = `SELECT COUNT(*) as count FROM "${schema}"."${table}"`;
		const result = await query<{ count: string }>(sql);

		if (!result.ok) {
			handleError(result, plain);
		}

		const count = Number(result.result.rows[0].count);
		const response: { ok: true } & CountResult = {
			ok: true,
			schema,
			table,
			count,
		};

		if (plain) {
			console.log(`${schema}.${table}: ${count.toLocaleString()} rows`);
			process.exit(0);
		}

		outputJson(response);
	},
});
