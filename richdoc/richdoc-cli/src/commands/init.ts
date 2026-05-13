import { existsSync } from "node:fs";
import { copyFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { defineCommand } from "citty";
import { ASSET_FILES, assetPath, assetsExist } from "../lib/assets.ts";
import { jsonError, jsonOk } from "../lib/output.ts";

export const initCommand = defineCommand({
	meta: {
		name: "init",
		description:
			"Copy richdoc.css and richdoc.js into a directory so .html files can link them via './richdoc.css' / './richdoc.js'.",
	},
	args: {
		dir: {
			type: "positional",
			description: "Target directory (default: current directory)",
			required: false,
			default: ".",
		},
		force: {
			type: "boolean",
			alias: "f",
			description: "Overwrite existing richdoc.css / richdoc.js in target",
			default: false,
		},
	},
	async run({ args }) {
		if (!assetsExist()) {
			jsonError(
				"Shipped assets are missing from the richdoc skill installation.",
				"INPUT_ERROR",
				"Ensure the skill folder contains both assets/richdoc.css and assets/richdoc.js.",
			);
		}

		const dir = resolve(args.dir);
		try {
			await mkdir(dir, { recursive: true });
		} catch (err) {
			const reason = err instanceof Error ? err.message : "unknown error";
			jsonError(`Could not create target directory: ${reason}`, "OUTPUT_ERROR");
		}

		const written: string[] = [];
		const skipped: string[] = [];
		for (const f of ASSET_FILES) {
			const target = resolve(dir, f);
			if (existsSync(target) && !args.force) {
				skipped.push(f);
				continue;
			}
			try {
				await copyFile(assetPath(f), target);
				written.push(f);
			} catch (err) {
				const reason = err instanceof Error ? err.message : "unknown error";
				jsonError(`Could not write ${f}: ${reason}`, "OUTPUT_ERROR");
			}
		}

		jsonOk({
			dir,
			written,
			skipped,
			hint: skipped.length
				? "Some files already existed and were left alone. Re-run with --force to overwrite."
				: undefined,
		});
	},
});
