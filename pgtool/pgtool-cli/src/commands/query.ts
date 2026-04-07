import { defineCommand } from "citty";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatTable, outputJson } from "../lib/output";

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
