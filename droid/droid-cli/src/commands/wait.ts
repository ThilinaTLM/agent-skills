import { defineCommand } from "citty";
import { jsonOk } from "../lib/output.ts";
import { sleep } from "../lib/sleep.ts";

export const waitCommand = defineCommand({
	meta: {
		name: "wait",
		description: "Wait for specified milliseconds",
	},
	args: {
		ms: {
			type: "positional",
			description: "Milliseconds to wait",
			required: true,
		},
	},
	async run({ args }) {
		const ms = Number.parseInt(args.ms, 10);
		await sleep(ms);
		jsonOk({ action: "wait", ms });
	},
});
