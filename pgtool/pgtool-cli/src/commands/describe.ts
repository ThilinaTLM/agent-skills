import { defineCommand } from "citty";
import { getDefaultSchema } from "../lib/config";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatBytes, formatTable, outputJson } from "../lib/output";
import type { ColumnInfo, DescribeResult, ForeignKeyRef } from "../types";

export const describeCommand = defineCommand({
	meta: {
		name: "describe",
		description: "Describe table columns with PK/FK info",
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

		// Parse table name (may include schema prefix)
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

		// Get columns with primary key and foreign key info
		const columnsResult = await query<{
			column_name: string;
			data_type: string;
			is_nullable: string;
			column_default: string | null;
			is_pk: boolean;
			is_fk: boolean;
			fk_schema: string | null;
			fk_table: string | null;
			fk_column: string | null;
			description: string | null;
		}>(
			`
      WITH pk_columns AS (
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = ($1 || '.' || $2)::regclass
          AND i.indisprimary
      ),
      fk_columns AS (
        SELECT
          kcu.column_name,
          ccu.table_schema AS fk_schema,
          ccu.table_name AS fk_table,
          ccu.column_name AS fk_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = $1
          AND tc.table_name = $2
      )
      SELECT
        c.column_name,
        c.data_type ||
          CASE
            WHEN c.character_maximum_length IS NOT NULL
              THEN '(' || c.character_maximum_length || ')'
            WHEN c.numeric_precision IS NOT NULL AND c.numeric_scale IS NOT NULL
              THEN '(' || c.numeric_precision || ',' || c.numeric_scale || ')'
            ELSE ''
          END AS data_type,
        c.is_nullable,
        c.column_default,
        COALESCE(pk.attname IS NOT NULL, false) AS is_pk,
        COALESCE(fk.column_name IS NOT NULL, false) AS is_fk,
        fk.fk_schema,
        fk.fk_table,
        fk.fk_column,
        pd.description
      FROM information_schema.columns c
      LEFT JOIN pk_columns pk ON pk.attname = c.column_name
      LEFT JOIN fk_columns fk ON fk.column_name = c.column_name
      LEFT JOIN pg_catalog.pg_statio_all_tables st
        ON st.schemaname = c.table_schema AND st.relname = c.table_name
      LEFT JOIN pg_catalog.pg_description pd
        ON pd.objoid = st.relid AND pd.objsubid = c.ordinal_position
      WHERE c.table_schema = $1 AND c.table_name = $2
      ORDER BY c.ordinal_position
    `,
			[schema, tableName],
		);

		if (!columnsResult.ok) {
			handleError(columnsResult, plain);
		}

		if (columnsResult.result.rows.length === 0) {
			handleError(
				{
					ok: false,
					error: `Table '${schema}.${tableName}' not found`,
					code: "TABLE_NOT_FOUND",
					hint: `Check that the table exists. Use 'pgtool tables ${schema}' to list available tables.`,
				},
				plain,
			);
		}

		// Get table stats
		const statsResult = await query<{
			row_estimate: string;
			size_bytes: string;
		}>(
			`
      SELECT
        c.reltuples::bigint AS row_estimate,
        pg_catalog.pg_table_size(c.oid)::bigint AS size_bytes
      FROM pg_catalog.pg_class c
      LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = $1 AND c.relname = $2
    `,
			[schema, tableName],
		);

		const columns: ColumnInfo[] = columnsResult.result.rows.map((row) => {
			let foreignKeyRef: ForeignKeyRef | null = null;
			if (row.is_fk && row.fk_schema && row.fk_table && row.fk_column) {
				foreignKeyRef = {
					schema: row.fk_schema,
					table: row.fk_table,
					column: row.fk_column,
				};
			}

			return {
				name: row.column_name,
				type: row.data_type,
				nullable: row.is_nullable === "YES",
				defaultValue: row.column_default,
				isPrimaryKey: row.is_pk,
				isForeignKey: row.is_fk,
				foreignKeyRef,
				comment: row.description,
			};
		});

		const stats = statsResult.ok ? statsResult.result.rows[0] : null;
		const sizeBytes = stats ? Number(stats.size_bytes) : null;

		const response: { ok: true } & DescribeResult = {
			ok: true,
			schema,
			table: tableName,
			columns,
			rowEstimate: stats ? Number(stats.row_estimate) : 0,
			sizeHuman: formatBytes(sizeBytes),
		};

		if (plain) {
			console.log(`Table: ${schema}.${tableName}`);
			if (stats) {
				console.log(
					`Rows: ~${Number(stats.row_estimate).toLocaleString()}  Size: ${formatBytes(sizeBytes) ?? "N/A"}`,
				);
			}
			console.log();

			console.log(
				formatTable(
					["Column", "Type", "Nullable", "Default", "Key", "Reference"],
					columns.map((c) => {
						const keys: string[] = [];
						if (c.isPrimaryKey) keys.push("PK");
						if (c.isForeignKey) keys.push("FK");

						let ref = "";
						if (c.foreignKeyRef) {
							ref = `${c.foreignKeyRef.schema}.${c.foreignKeyRef.table}.${c.foreignKeyRef.column}`;
						}

						return [
							c.name,
							c.type,
							c.nullable ? "YES" : "NO",
							c.defaultValue ?? "",
							keys.join(","),
							ref,
						];
					}),
				),
			);
			process.exit(0);
		}

		outputJson(response);
	},
});
