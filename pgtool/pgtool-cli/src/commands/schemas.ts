import { defineCommand } from "citty";
import { query } from "../lib/connection";
import { handleError, initPgTool, registerCleanup } from "../lib/init";
import { formatTable, outputJson } from "../lib/output";
import type { SchemaInfo, SchemasResult } from "../types";

export const schemasCommand = defineCommand({
	meta: {
		name: "schemas",
		description: "List all database schemas",
	},
	args: {
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

		const result = await query<{ schema_name: string; owner: string }>(`
      SELECT
        n.nspname AS schema_name,
        pg_catalog.pg_get_userbyid(n.nspowner) AS owner
      FROM pg_catalog.pg_namespace n
      WHERE n.nspname !~ '^pg_'
        AND n.nspname <> 'information_schema'
      ORDER BY schema_name
    `);

		if (!result.ok) {
			handleError(result, plain);
		}

		const schemas: SchemaInfo[] = result.result.rows.map((row) => ({
			name: row.schema_name,
			owner: row.owner,
		}));

		const response: { ok: true } & SchemasResult = {
			ok: true,
			schemas,
		};

		if (plain) {
			if (schemas.length === 0) {
				console.log("No schemas found");
			} else {
				console.log(
					formatTable(
						["Schema", "Owner"],
						schemas.map((s) => [s.name, s.owner]),
					),
				);
			}
			process.exit(0);
		}

		outputJson(response);
	},
});
