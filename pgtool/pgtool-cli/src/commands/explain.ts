import { defineCommand } from "citty";
import { globalArgs, initOptsFromArgs } from "../lib/args.ts";
import { query } from "../lib/connection.ts";
import {
	handleError,
	initDaemonConnection,
	initPgTool,
	registerCleanup,
} from "../lib/init.ts";
import { outputJson } from "../lib/output.ts";
import type { ExplainResult } from "../types";

export const explainCommand = defineCommand({
	meta: {
		name: "explain",
		description: "Show query execution plan",
	},
	args: {
		sql: {
			type: "positional",
			description: "SQL query to explain",
			required: true,
		},
		...globalArgs,
		"no-analyze": {
			type: "boolean",
			description: "Use EXPLAIN without ANALYZE (no execution)",
		},
	},
	async run({ args }) {
		const plain = args.plain ?? false;
		initPgTool(initOptsFromArgs(args));
		registerCleanup();
		await initDaemonConnection();

		const noAnalyze = args["no-analyze"] ?? false;
		const explainPrefix = noAnalyze ? "EXPLAIN" : "EXPLAIN ANALYZE";
		const sql = `${explainPrefix} ${args.sql}`;

		const result = await query<{ "QUERY PLAN": string }>(sql);

		if (!result.ok) {
			handleError(result, plain);
		}

		const plan = result.result.rows.map((row) => row["QUERY PLAN"]);

		const response: { ok: true } & ExplainResult = {
			ok: true,
			query: args.sql,
			plan,
		};

		if (plain) {
			console.log(`Query Plan${noAnalyze ? "" : " (with ANALYZE)"}:\n`);
			for (const line of plan) {
				console.log(line);
			}
			process.exit(0);
		}

		outputJson(response);
	},
});
