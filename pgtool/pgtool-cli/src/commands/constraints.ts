import { defineCommand } from "citty";
import { getDefaultSchema } from "../lib/config";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatTable, outputJson } from "../lib/output";
import type { ConstraintInfo, ConstraintsResult } from "../types";

export const constraintsCommand = defineCommand({
	meta: {
		name: "constraints",
		description: "List constraints (PK, FK, unique, check) on a table",
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
			constraint_name: string;
			constraint_type: string;
			columns: string;
			definition: string;
			foreign_table: string | null;
			foreign_columns: string | null;
		}>(
			`
      SELECT
        c.conname AS constraint_name,
        CASE c.contype
          WHEN 'p' THEN 'PRIMARY KEY'
          WHEN 'f' THEN 'FOREIGN KEY'
          WHEN 'u' THEN 'UNIQUE'
          WHEN 'c' THEN 'CHECK'
          WHEN 'x' THEN 'EXCLUDE'
        END AS constraint_type,
        array_to_string(array_agg(DISTINCT a.attname ORDER BY a.attname), ', ') AS columns,
        pg_catalog.pg_get_constraintdef(c.oid) AS definition,
        CASE WHEN c.contype = 'f'
          THEN (SELECT nspname || '.' || relname FROM pg_class r JOIN pg_namespace n ON n.oid = r.relnamespace WHERE r.oid = c.confrelid)
          ELSE NULL
        END AS foreign_table,
        CASE WHEN c.contype = 'f'
          THEN (
            SELECT array_to_string(array_agg(fa.attname ORDER BY array_position(c.confkey, fa.attnum)), ', ')
            FROM pg_attribute fa
            WHERE fa.attrelid = c.confrelid AND fa.attnum = ANY(c.confkey)
          )
          ELSE NULL
        END AS foreign_columns
      FROM pg_catalog.pg_constraint c
      JOIN pg_catalog.pg_class t ON t.oid = c.conrelid
      JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace
      LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
      WHERE n.nspname = $1 AND t.relname = $2
      GROUP BY c.conname, c.contype, c.oid, c.confrelid, c.confkey
      ORDER BY
        CASE c.contype
          WHEN 'p' THEN 1
          WHEN 'f' THEN 2
          WHEN 'u' THEN 3
          WHEN 'c' THEN 4
          WHEN 'x' THEN 5
        END,
        c.conname
    `,
			[schema, tableName],
		);

		if (!result.ok) {
			handleError(result, plain);
		}

		const constraints: ConstraintInfo[] = result.result.rows.map((row) => {
			const constraint: ConstraintInfo = {
				name: row.constraint_name,
				type: row.constraint_type as ConstraintInfo["type"],
				columns: row.columns ? row.columns.split(", ") : [],
				definition: row.definition,
			};

			if (row.foreign_table) {
				constraint.foreignTable = row.foreign_table;
			}
			if (row.foreign_columns) {
				constraint.foreignColumns = row.foreign_columns.split(", ");
			}

			return constraint;
		});

		const response: { ok: true } & ConstraintsResult = {
			ok: true,
			schema,
			table: tableName,
			constraints,
		};

		if (plain) {
			console.log(`Constraints on ${schema}.${tableName}:\n`);
			if (constraints.length === 0) {
				console.log("No constraints found");
			} else {
				console.log(
					formatTable(
						["Name", "Type", "Columns", "References"],
						constraints.map((c) => [
							c.name,
							c.type,
							c.columns.join(", "),
							c.foreignTable
								? `${c.foreignTable}(${c.foreignColumns?.join(", ") ?? ""})`
								: "",
						]),
					),
				);
			}
			process.exit(0);
		}

		outputJson(response);
	},
});
