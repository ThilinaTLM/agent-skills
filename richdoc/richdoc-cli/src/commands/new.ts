import { existsSync } from "node:fs";
import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { defineCommand } from "citty";
import { ASSET_FILES } from "../lib/assets.ts";
import { jsonError, jsonOk } from "../lib/output.ts";
import {
	listTemplates,
	templateExists,
	templatePath,
} from "../lib/templates.ts";

const DEFAULT_TEMPLATE = "plan";

export const newCommand = defineCommand({
	meta: {
		name: "new",
		description:
			"Scaffold a new richdoc .html file from a template. Use `richdoc init` next to it to drop the CSS/JS assets.",
	},
	args: {
		output: {
			type: "positional",
			description: "Output .html path (e.g. docs/plan.html)",
			required: true,
		},
		template: {
			type: "string",
			alias: "t",
			description: `Template to use (default: ${DEFAULT_TEMPLATE})`,
			default: DEFAULT_TEMPLATE,
		},
		force: {
			type: "boolean",
			alias: "f",
			description: "Overwrite the output file if it exists",
			default: false,
		},
	},
	async run({ args }) {
		const tplName = args.template || DEFAULT_TEMPLATE;
		const available = listTemplates();
		if (!templateExists(tplName)) {
			jsonError(
				`Unknown template '${tplName}'.`,
				"TEMPLATE_NOT_FOUND",
				`Available templates: ${available.join(", ")}`,
				{ available },
			);
		}

		const output = resolve(args.output);
		if (!output.toLowerCase().endsWith(".html")) {
			jsonError(
				`Output path must end with .html (got '${output}').`,
				"INVALID_PARAMS",
			);
		}
		if (existsSync(output) && !args.force) {
			jsonError(
				`Output file already exists: ${output}`,
				"FILE_EXISTS",
				"Re-run with --force to overwrite.",
				{ file: output },
			);
		}

		try {
			await mkdir(dirname(output), { recursive: true });
			await copyFile(templatePath(tplName), output);
		} catch (err) {
			const reason = err instanceof Error ? err.message : "unknown error";
			jsonError(`Could not write output: ${reason}`, "OUTPUT_ERROR");
		}

		// Check whether the assets are present next to the output. If not,
		// surface a hint — the linked `./richdoc.css` / `./richdoc.js` won't
		// resolve until `richdoc init` runs in the same directory.
		const dir = dirname(output);
		const missing = ASSET_FILES.filter((f) => !existsSync(resolve(dir, f)));

		jsonOk({
			file: output,
			template: tplName,
			assets_needed: missing,
			hint: missing.length
				? `Run \`richdoc init ${dir}\` to drop the CSS/JS assets next to this file.`
				: undefined,
		});
	},
});
