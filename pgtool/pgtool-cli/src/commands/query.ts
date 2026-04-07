import { defineCommand } from "citty";
import { globalArgs, initOptsFromArgs } from "../lib/args.ts";
import { query } from "../lib/connection.ts";
import {
	handleError,
	initDaemonConnection,
	initPgTool,
	registerCleanup,
} from "../lib/init.ts";
import { formatTable, outputJson } from "../lib/output.ts";

export const queryCommand = defineCommand({
	meta: {
		name: "query",
		description: "Execute a SQL query",
	},
	args: {
		sql: {
			type: "positional",
			description: "SQL query to execute",
			required: true,
		},
		...globalArgs,
	},
	async run({ args }) {
		const plain = args.plain ?? false;
		initPgTool(initOptsFromArgs(args));
		registerCleanup();
		await initDaemonConnection();

		const sql = args.sql;

		const result = await query(sql);

		if (!result.ok) {
			handleError(result, plain);
		}

		const response = {
			ok: true as const,
			rows: result.result.rows,
			rowCount: result.result.rowCount,
			fields: result.result.fields.map((f) => f.name),
		};

		if (plain) {
			if (result.result.rows.length === 0) {
				console.log("No rows returned");
				process.exit(0);
			}

			const fields = result.result.fields.map((f) => f.name);
			const rows = result.result.rows.map((row) =>
				fields.map((f) => {
					const value = row[f];
					if (value === null) return "NULL";
					if (typeof value === "object") return JSON.stringify(value);
					return String(value);
				}),
			);

			console.log(formatTable(fields, rows));
			console.log(
				`\n(${result.result.rowCount} row${result.result.rowCount !== 1 ? "s" : ""})`,
			);
			process.exit(0);
		}

		outputJson(response);
	},
});
