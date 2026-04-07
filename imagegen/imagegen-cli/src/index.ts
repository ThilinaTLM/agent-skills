#!/usr/bin/env bun
import { defineCommand, runMain } from "citty";
import pkg from "../package.json";
import { generateCommand } from "./commands/generate";

const main = defineCommand({
	meta: {
		name: "imagegen",
		version: pkg.version,
		description: "AI image generation via Google Gemini",
	},
	subCommands: {
		generate: generateCommand,
		gen: generateCommand,
	},
});

runMain(main);
