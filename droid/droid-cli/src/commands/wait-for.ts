import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonOk } from "../lib/output";
import { dumpUIHierarchy } from "../lib/ui-hierarchy";

export const waitForCommand = defineCommand({
	meta: {
		name: "wait-for",
		description: "Wait for an element to appear on screen",
	},
	args: {
		text: {
			type: "string",
			alias: "t",
			description: "Text to wait for",
			required: true,
		},
		timeout: {
			type: "string",
			alias: "s",
			default: "10",
			description: "Timeout in seconds (default: 10)",
		},
	},
	async run({ args }) {
		const adb = new ADB();
		await adb.getDevice();

		const timeoutMs = Number.parseInt(args.timeout, 10) * 1000;
		const pollInterval = 250; // Reduced from 500ms for faster detection
		const start = Date.now();

		while (Date.now() - start < timeoutMs) {
			const elements = await dumpUIHierarchy(adb);
			const matches = elements.filter((e) => e.matches(args.text));

			if (matches.length > 0) {
				const elem = matches[0];
				jsonOk({
					action: "wait_for",
					found: true,
					element: elem.toDict(),
					elapsed_ms: Date.now() - start,
				});
			}

			await Bun.sleep(pollInterval);
		}

		// Timeout - include searched text for debugging
		jsonOk({
			action: "wait_for",
			found: false,
			timeout: true,
			searched: args.text,
			elapsed_ms: Date.now() - start,
		});
	},
});
