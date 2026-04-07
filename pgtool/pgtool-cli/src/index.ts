import { defineCommand, runMain } from "citty";
import pkg from "../package.json" with { type: "json" };
// Version 3.0.0 — multi-profile, read-only, daemon, protected profiles
import { constraintsCommand } from "./commands/constraints.ts";
import { countCommand } from "./commands/count.ts";
import { daemonCommand } from "./commands/daemon.ts";
import { describeCommand } from "./commands/describe.ts";
import { explainCommand } from "./commands/explain.ts";
import { indexesCommand } from "./commands/indexes.ts";
import { overviewCommand } from "./commands/overview.ts";
import { profilesCommand } from "./commands/profiles.ts";
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
	// All args (root, plain, profile, read-only, allow-writes) are defined
	// in globalArgs and spread into each subcommand — not here.
	// Citty's parent-level string args consume the next positional token,
	// which conflicts with subcommand routing (e.g., `pgtool -p dev schemas`
	// would parse `dev` as a subcommand name, not a profile value).
	subCommands: {
		profiles: profilesCommand,
		daemon: daemonCommand,
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
