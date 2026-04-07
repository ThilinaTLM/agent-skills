import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonOk } from "../lib/output";

export const hideKeyboardCommand = defineCommand({
	meta: {
		name: "hide-keyboard",
		description: "Dismiss the on-screen keyboard",
	},
	args: {
		wait: {
			type: "string",
			alias: "w",
			description: "Wait ms after action",
		},
	},
	async run({ args }) {
		const adb = new ADB();
		await adb.getDevice();

		// Send ESCAPE key to dismiss keyboard without navigating back
		await adb.shell("input", "keyevent", "111");

		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		jsonOk({ action: "hide_keyboard" });
	},
});
