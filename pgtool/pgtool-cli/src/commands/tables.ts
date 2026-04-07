import { defineCommand } from "citty";
import { getDefaultSchema } from "../lib/config";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatBytes, formatTable, outputJson } from "../lib/output";
import type { TableInfo, TablesResult } from "../types";

export const tablesCommand = defineCommand({
	meta: {
		name: "tables",
		description: "List tables in a schema",
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
			table_name: string;
			table_type: string;
			owner: string;
			row_estimate: string;
			size_bytes: string | null;
		}>(
			`
      SELECT
        c.relname AS table_name,
        CASE c.relkind
          WHEN 'r' THEN 'table'
          WHEN 'v' THEN 'view'
          WHEN 'm' THEN 'materialized view'
          WHEN 'f' THEN 'foreign table'
        END AS table_type,
        pg_catalog.pg_get_userbyid(c.relowner) AS owner,
        c.reltuples::bigint AS row_estimate,
        pg_catalog.pg_table_size(c.oid)::bigint AS size_bytes
      FROM pg_catalog.pg_class c
      LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = $1
        AND c.relkind IN ('r', 'v', 'm', 'f')
      ORDER BY c.relname
    `,
			[schema],
		);

		if (!result.ok) {
			handleError(result, plain);
		}

		const tables: TableInfo[] = result.result.rows.map((row) => {
			const sizeBytes = row.size_bytes ? Number(row.size_bytes) : null;
			const rowEstimateRaw = Number(row.row_estimate);
			return {
				name: row.table_name,
				schema,
				type: row.table_type as TableInfo["type"],
				owner: row.owner,
				rowEstimate: rowEstimateRaw,
				rowEstimateUnknown: rowEstimateRaw < 0,
				sizeBytes,
				sizeHuman: formatBytes(sizeBytes),
			};
		});

		// Check if any tables have unknown row estimates
		const hasUnknownEstimates = tables.some((t) => t.rowEstimateUnknown);

		const response: { ok: true; hint?: string } & TablesResult = {
			ok: true,
			schema,
			tables,
			...(hasUnknownEstimates && {
				hint: "Run ANALYZE <tablename> for accurate row estimates",
			}),
		};

		if (plain) {
			console.log(`Tables in schema '${schema}':\n`);
			if (tables.length === 0) {
				console.log("No tables found");
			} else {
				console.log(
					formatTable(
						["Name", "Type", "Rows", "Size"],
						tables.map((t) => [
							t.name,
							t.type,
							t.rowEstimateUnknown ? "unknown" : t.rowEstimate.toLocaleString(),
							t.sizeHuman ?? "N/A",
						]),
					),
				);
				if (hasUnknownEstimates) {
					console.log(
						"\nHint: Run ANALYZE <tablename> for accurate row estimates",
					);
				}
			}
			process.exit(0);
		}

		outputJson(response);
	},
});
