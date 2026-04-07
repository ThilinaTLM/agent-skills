import { defineCommand } from "citty";
import { ADB } from "../lib/adb.ts";
import { KEY_CODES } from "../lib/keycodes.ts";
import { jsonError, jsonOk } from "../lib/output.ts";
import { sleep } from "../lib/sleep.ts";

export const keyCommand = defineCommand({
	meta: {
		name: "key",
		description: "Send key event",
	},
	args: {
		key: {
			type: "positional",
			description: "Key name or code",
			required: true,
		},
		wait: {
			type: "string",
			alias: "w",
			description: "Wait ms after key",
		},
	},
	async run({ args }) {
		const adb = new ADB();
		await adb.getDevice();

		const key = args.key.toLowerCase();
		let keycode: number;

		if (key in KEY_CODES) {
			keycode = KEY_CODES[key];
		} else if (/^\d+$/.test(key)) {
			keycode = Number.parseInt(key, 10);
		} else {
			jsonError(
				`Unknown key: ${key}. Available: ${Object.keys(KEY_CODES).join(", ")}`,
				"INVALID_KEY",
			);
		}

		await adb.shell("input", "keyevent", String(keycode));

		if (args.wait) {
			await sleep(Number.parseInt(args.wait, 10));
		}

		jsonOk({ action: "key", key: args.key, keycode });
	},
});
