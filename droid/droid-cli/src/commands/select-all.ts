import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonOk } from "../lib/output";

export const selectAllCommand = defineCommand({
	meta: {
		name: "select-all",
		description: "Select all text in the currently focused field",
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

		// Try Ctrl+A using keyevent with meta modifier flag
		// META_CTRL_ON = 0x1000 (4096 decimal)
		// This should work on Android 11+
		// Format: input keyevent --meta <meta_state> <keycode>
		const result = await adb.shellUnchecked(
			"input",
			"keyevent",
			"--meta",
			"4096",
			"29",
		);

		// If that failed (older Android), fall back to sequential approach
		if (
			result.stdout.includes("Unknown") ||
			result.stderr.toLowerCase().includes("error")
		) {
			// Try the sequential key press (less reliable but worth trying)
			await adb.shell("input", "keyevent", "113"); // CTRL_LEFT down
			await adb.shell("input", "keyevent", "29"); // A
			await adb.shell("input", "keyevent", "113"); // CTRL_LEFT up
		}

		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		jsonOk({ action: "select_all" });
	},
});
