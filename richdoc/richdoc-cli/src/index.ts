import { defineCommand, runMain } from "citty";
import pkg from "../package.json" with { type: "json" };
import { buildCommand } from "./commands/build.ts";
import { componentsCommand } from "./commands/components.ts";
import { initCommand } from "./commands/init.ts";
import { lintCommand } from "./commands/lint.ts";
import { newCommand } from "./commands/new.ts";

const main = defineCommand({
	meta: {
		name: "richdoc",
		version: pkg.version,
		description:
			"Scaffold, validate, and ship rich HTML documents built from the richdoc component vocabulary.",
	},
	subCommands: {
		new: newCommand,
		init: initCommand,
		lint: lintCommand,
		build: buildCommand,
		components: componentsCommand,
	},
});

runMain(main);
