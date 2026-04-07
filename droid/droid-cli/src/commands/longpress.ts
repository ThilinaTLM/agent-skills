import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonError, jsonOk } from "../lib/output";
import { dumpUIHierarchy } from "../lib/ui-hierarchy";

export const longpressCommand = defineCommand({
	meta: {
		name: "longpress",
		description: "Long press at coordinates or by text",
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
			description: "Find and long press element by text",
		},
		index: {
			type: "string",
			alias: "i",
			default: "0",
			description: "Index if multiple matches",
		},
		duration: {
			type: "string",
			alias: "d",
			default: "1000",
			description: "Press duration in ms (default: 1000)",
		},
		wait: {
			type: "string",
			alias: "w",
			description: "Wait ms after action",
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
			const matches = elements.filter((e) => e.matches(args.text as string));

			if (matches.length === 0) {
				jsonError(
					`No element found matching '${args.text}'`,
					"ELEMENT_NOT_FOUND",
				);
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
				"Specify coordinates (longpress X Y) or text (longpress -t TEXT)",
				"INVALID_ARGS",
			);
		}

		// Long press = swipe from same point to same point with long duration
		const duration = args.duration;
		await adb.shell(
			"input",
			"swipe",
			String(x),
			String(y),
			String(x),
			String(y),
			duration,
		);

		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		const result: Record<string, unknown> = {
			action: "longpress",
			x,
			y,
			duration: Number.parseInt(duration, 10),
		};
		if (matchedText) {
			result.matched = matchedText;
		}

		jsonOk(result);
	},
});
