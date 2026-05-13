import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineCommand } from "citty";
import { jsonError, jsonOk } from "../lib/output.ts";

/**
 * Locate the richdoc framework root (the folder containing `build.ts`).
 * The CLI lives at `<root>/richdoc-cli/src/commands/build.ts`, so walk up
 * three levels.
 */
function frameworkRoot(): string {
	const here = dirname(fileURLToPath(import.meta.url));
	return resolve(here, "..", "..", "..");
}

export const buildCommand = defineCommand({
	meta: {
		name: "build",
		description:
			"Rebuild richdoc.js, richdoc.css, schema.json, and version.txt from src/.",
	},
	args: {
		dev: {
			type: "boolean",
			description: "Skip minification; emit larger, source-mapped output.",
			default: false,
		},
	},
	async run({ args }) {
		const root = frameworkRoot();
		const buildScript = resolve(root, "build.ts");
		if (!existsSync(buildScript)) {
			jsonError(
				`No build.ts found at ${buildScript}. Are you running from a richdoc framework checkout?`,
				"BUILD_NOT_FOUND",
			);
		}

		const cmd = ["bun", "run", buildScript];
		if (args.dev) cmd.push("--dev");

		const proc = Bun.spawn(cmd, {
			cwd: root,
			stdout: "pipe",
			stderr: "pipe",
		});
		const stdout = await new Response(proc.stdout).text();
		const stderr = await new Response(proc.stderr).text();
		const code = await proc.exited;

		if (code !== 0) {
			jsonError(`Build failed (exit ${code}).`, "BUILD_FAILED", undefined, {
				stdout,
				stderr,
				exitCode: code,
			});
		}

		// Read the produced version stamp so the caller can confirm what shipped.
		let version: unknown = null;
		try {
			const versionFile = resolve(root, "assets", "version.txt");
			version = JSON.parse(await Bun.file(versionFile).text());
		} catch {
			// Non-fatal; build succeeded, version stamp just wasn't readable.
		}

		jsonOk({
			ok: true,
			root,
			dev: !!args.dev,
			version,
			log: stdout.trim(),
		});
	},
});
