import { defineCommand } from "citty";
import { getDefaultSchema } from "../lib/config";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { outputJson } from "../lib/output";
import type { OverviewResult, OverviewTable } from "../types";

export const overviewCommand = defineCommand({
	meta: {
		name: "overview",
		description: "Show schema overview with tables, keys, and relationships",
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

		// Get tables with row estimates
		const tablesResult = await query<{
			table_name: string;
			row_estimate: string;
		}>(
			`
      SELECT
        c.relname AS table_name,
        c.reltuples::bigint AS row_estimate
      FROM pg_catalog.pg_class c
      LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = $1
        AND c.relkind = 'r'
      ORDER BY c.relname
      `,
			[schema],
		);

		if (!tablesResult.ok) {
			handleError(tablesResult, plain);
		}

		// Get primary keys
		const pkResult = await query<{
			table_name: string;
			column_name: string;
		}>(
			`
      SELECT
        c.relname AS table_name,
        a.attname AS column_name
      FROM pg_catalog.pg_constraint con
      JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(con.conkey)
      WHERE con.contype = 'p'
        AND n.nspname = $1
      ORDER BY c.relname, a.attnum
      `,
			[schema],
		);

		if (!pkResult.ok) {
			handleError(pkResult, plain);
		}

		// Get foreign keys (outgoing from tables in this schema)
		const fkResult = await query<{
			from_table: string;
			from_column: string;
			to_table: string;
			to_column: string;
		}>(
			`
      SELECT
        c.relname AS from_table,
        a.attname AS from_column,
        fc.relname AS to_table,
        fa.attname AS to_column
      FROM pg_catalog.pg_constraint con
      JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_catalog.pg_class fc ON fc.oid = con.confrelid
      JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(con.conkey)
      JOIN pg_catalog.pg_attribute fa ON fa.attrelid = fc.oid AND fa.attnum = ANY(con.confkey)
      WHERE con.contype = 'f'
        AND n.nspname = $1
      ORDER BY c.relname, a.attnum
      `,
			[schema],
		);

		if (!fkResult.ok) {
			handleError(fkResult, plain);
		}

		// Get references to tables in this schema (incoming foreign keys)
		const refsResult = await query<{
			to_table: string;
			from_table: string;
			from_column: string;
		}>(
			`
      SELECT
        fc.relname AS to_table,
        c.relname AS from_table,
        a.attname AS from_column
      FROM pg_catalog.pg_constraint con
      JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
      JOIN pg_catalog.pg_class fc ON fc.oid = con.confrelid
      JOIN pg_catalog.pg_namespace fn ON fn.oid = fc.relnamespace
      JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(con.conkey)
      WHERE con.contype = 'f'
        AND fn.nspname = $1
      ORDER BY fc.relname, c.relname
      `,
			[schema],
		);

		if (!refsResult.ok) {
			handleError(refsResult, plain);
		}

		// Build primary key map
		const pkMap = new Map<string, string[]>();
		for (const row of pkResult.result.rows) {
			const existing = pkMap.get(row.table_name) || [];
			existing.push(row.column_name);
			pkMap.set(row.table_name, existing);
		}

		// Build foreign key map
		const fkMap = new Map<
			string,
			Array<{ column: string; references: { table: string; column: string } }>
		>();
		for (const row of fkResult.result.rows) {
			const existing = fkMap.get(row.from_table) || [];
			existing.push({
				column: row.from_column,
				references: { table: row.to_table, column: row.to_column },
			});
			fkMap.set(row.from_table, existing);
		}

		// Build referenced-by map
		const refsMap = new Map<string, Array<{ table: string; column: string }>>();
		for (const row of refsResult.result.rows) {
			const existing = refsMap.get(row.to_table) || [];
			existing.push({ table: row.from_table, column: row.from_column });
			refsMap.set(row.to_table, existing);
		}

		// Build tables array
		const tables: OverviewTable[] = tablesResult.result.rows.map((row) => {
			const rowEstimateRaw = Number(row.row_estimate);
			return {
				name: row.table_name,
				rowEstimate: rowEstimateRaw < 0 ? "unknown" : rowEstimateRaw,
				primaryKey: pkMap.get(row.table_name) || [],
				foreignKeys: fkMap.get(row.table_name) || [],
				referencedBy: refsMap.get(row.table_name) || [],
			};
		});

		const response: { ok: true } & OverviewResult = {
			ok: true,
			schema,
			tableCount: tables.length,
			tables,
		};

		if (plain) {
			console.log(`Schema: ${schema} (${tables.length} tables)\n`);

			if (tables.length === 0) {
				console.log("No tables found");
				process.exit(0);
			}

			for (const t of tables) {
				const rowStr =
					t.rowEstimate === "unknown"
						? "unknown"
						: formatRowCount(t.rowEstimate);
				console.log(`${t.name} (${rowStr} rows)`);

				if (t.primaryKey.length > 0) {
					console.log(`  PK: ${t.primaryKey.join(", ")}`);
				}

				for (const fk of t.foreignKeys) {
					console.log(
						`  FK: ${fk.column} → ${fk.references.table}.${fk.references.column}`,
					);
				}

				if (t.referencedBy.length > 0) {
					const refs = t.referencedBy
						.map((r) => `${r.table}.${r.column}`)
						.join(", ");
					console.log(`  → ${refs}`);
				}

				console.log();
			}

			process.exit(0);
		}

		outputJson(response);
	},
});

/**
 * Format row count in human-readable form (e.g., "1.2k", "45k", "1.2M")
 */
function formatRowCount(count: number): string {
	if (count < 1000) return String(count);
	if (count < 1000000) {
		const k = count / 1000;
		return k >= 10 ? `${Math.round(k)}k` : `${k.toFixed(1)}k`;
	}
	const m = count / 1000000;
	return m >= 10 ? `${Math.round(m)}M` : `${m.toFixed(1)}M`;
}
