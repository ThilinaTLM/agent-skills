#!/usr/bin/env bun
import { defineCommand, runMain } from "citty";
import pkg from "../package.json";
import { constraintsCommand } from "./commands/constraints";
import { countCommand } from "./commands/count";
import { describeCommand } from "./commands/describe";
import { explainCommand } from "./commands/explain";
import { indexesCommand } from "./commands/indexes";
import { overviewCommand } from "./commands/overview";
import { queryCommand } from "./commands/query";
import { relationshipsCommand } from "./commands/relationships";
import { sampleCommand } from "./commands/sample";
import { schemasCommand } from "./commands/schemas";
import { searchCommand } from "./commands/search";
import { tablesCommand } from "./commands/tables";

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
