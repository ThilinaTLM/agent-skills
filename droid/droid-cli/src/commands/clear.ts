import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonOk } from "../lib/output";

export const clearCommand = defineCommand({
	meta: {
		name: "clear",
		description: "Clear the currently focused text field",
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

		// Move cursor to end of text first
		await adb.shell("input", "keyevent", "123"); // KEYCODE_MOVE_END
		await Bun.sleep(50);

		// Delete all characters by sending multiple backspace keys
		// Most text fields are < 200 chars, send 200 deletes to be safe
		// We batch them in groups for efficiency
		for (let i = 0; i < 20; i++) {
			// Send 10 delete keys per batch
			await adb.shell(
				"input",
				"keyevent",
				"67",
				"67",
				"67",
				"67",
				"67",
				"67",
				"67",
				"67",
				"67",
				"67",
			);
		}

		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		jsonOk({ action: "clear" });
	},
});
