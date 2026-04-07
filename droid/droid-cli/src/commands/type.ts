import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonOk } from "../lib/output";

export const typeCommand = defineCommand({
	meta: {
		name: "type",
		description: "Type text into focused field",
	},
	args: {
		text: {
			type: "positional",
			description: "Text to type",
			required: true,
		},
		wait: {
			type: "string",
			alias: "w",
			description: "Wait ms after typing",
		},
	},
	async run({ args }) {
		const adb = new ADB();
		await adb.getDevice();

		// Escape text for adb: replace spaces with %s
		const escaped = args.text.replace(/ /g, "%s");
		await adb.shell("input", "text", escaped);

		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		jsonOk({ action: "type", text: args.text });
	},
});
