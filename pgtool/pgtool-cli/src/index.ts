import { defineCommand, runMain } from "citty";
import pkg from "../package.json" with { type: "json" };
import { constraintsCommand } from "./commands/constraints.ts";
import { countCommand } from "./commands/count.ts";
import { describeCommand } from "./commands/describe.ts";
import { explainCommand } from "./commands/explain.ts";
import { indexesCommand } from "./commands/indexes.ts";
import { overviewCommand } from "./commands/overview.ts";
import { queryCommand } from "./commands/query.ts";
import { relationshipsCommand } from "./commands/relationships.ts";
import { sampleCommand } from "./commands/sample.ts";
import { schemasCommand } from "./commands/schemas.ts";
import { searchCommand } from "./commands/search.ts";
import { tablesCommand } from "./commands/tables.ts";

const main = defineCommand({
	meta: {
		name: "pgtool",
		version: pkg.version,
		description: "PostgreSQL database exploration and debugging CLI",
	},
	args: {
		root: {
			type: "string",
			alias: "r",
			description:
				"Project root directory (default: auto-detect by walking up to find .pgtool.json)",
		},
		plain: {
			type: "boolean",
			description: "Human-readable output instead of JSON (JSON is default)",
		},
	},
	subCommands: {
		schemas: schemasCommand,
		tables: tablesCommand,
		describe: describeCommand,
		indexes: indexesCommand,
		constraints: constraintsCommand,
		relationships: relationshipsCommand,
		query: queryCommand,
		sample: sampleCommand,
		count: countCommand,
		search: searchCommand,
		overview: overviewCommand,
		explain: explainCommand,
	},
});

runMain(main);
