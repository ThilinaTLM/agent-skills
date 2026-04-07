import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonError, jsonOk } from "../lib/output";
import { dumpUIHierarchy } from "../lib/ui-hierarchy";

export const tapCommand = defineCommand({
	meta: {
		name: "tap",
		description: "Tap at coordinates or by text",
	},
	args: {
		x: {
			type: "positional",
			description: "X coordinate",
			required: false,
		},
		y: {
			type: "positional",
			description: "Y coordinate",
			required: false,
		},
		text: {
			type: "string",
			alias: "t",
			description: "Find and tap element by text",
		},
		index: {
			type: "string",
			alias: "i",
			default: "0",
			description: "Index if multiple matches",
		},
		wait: {
			type: "string",
			alias: "w",
			description: "Wait ms after tap",
		},
		"prefer-input": {
			type: "boolean",
			description: "Prefer input fields over labels",
		},
		clickable: {
			type: "boolean",
			description: "Only match clickable elements",
		},
	},
	async run({ args }) {
		const adb = new ADB();
		await adb.getDevice();

		let x: number | undefined;
		let y: number | undefined;
		let matchedText: string | undefined;

		if (args.text) {
			// Find element by text
			const elements = await dumpUIHierarchy(adb);
			let matches = elements.filter((e) => e.matches(args.text as string));

			if (matches.length === 0) {
				jsonError(
					`No element found matching '${args.text}'`,
					"ELEMENT_NOT_FOUND",
				);
			}

			// If --prefer-input, sort to put input fields first
			if (args["prefer-input"]) {
				matches.sort((a, b) => {
					if (a.isInputField() && !b.isInputField()) return -1;
					if (!a.isInputField() && b.isInputField()) return 1;
					return a.y - b.y;
				});
			}

			// If --clickable, filter to clickable elements only
			if (args.clickable) {
				matches = matches.filter((e) => e.clickable);
				if (matches.length === 0) {
					jsonError(
						`No clickable element found matching '${args.text}'`,
						"ELEMENT_NOT_FOUND",
					);
				}
			}

			const index = Number.parseInt(args.index, 10);
			if (index >= matches.length) {
				jsonError(
					`Index ${index} out of range (found ${matches.length} matches)`,
					"INVALID_ARGS",
				);
			}

			const elem = matches[index];
			x = elem.x;
			y = elem.y;
			matchedText = elem.text || elem.contentDesc || elem.resourceId;
		} else if (args.x !== undefined && args.y !== undefined) {
			x = Number.parseInt(args.x as string, 10);
			y = Number.parseInt(args.y as string, 10);
		} else {
			jsonError(
				"Specify coordinates (tap X Y) or text (tap -t TEXT)",
				"INVALID_ARGS",
			);
		}

		// Perform tap
		await adb.shell("input", "tap", String(x), String(y));

		// Wait if specified
		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		const result: Record<string, unknown> = { action: "tap", x, y };
		if (matchedText) {
			result.matched = matchedText;
		}

		jsonOk(result);
	},
});
