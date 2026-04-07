import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonError, jsonOk } from "../lib/output";
import { dumpUIHierarchy } from "../lib/ui-hierarchy";

export const fillCommand = defineCommand({
	meta: {
		name: "fill",
		description: "Fill a text field (tap + clear + type + hide-keyboard)",
	},
	args: {
		field: {
			type: "positional",
			description: "Field text to find",
			required: true,
		},
		value: {
			type: "positional",
			description: "Value to type",
			required: true,
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

		// Find the element
		const elements = await dumpUIHierarchy(adb);
		const matches = elements.filter((e) => e.matches(args.field));

		if (matches.length === 0) {
			jsonError(
				`No element found matching '${args.field}'`,
				"ELEMENT_NOT_FOUND",
			);
		}

		// Sort to prefer input fields
		matches.sort((a, b) => {
			if (a.isInputField() && !b.isInputField()) return -1;
			if (!a.isInputField() && b.isInputField()) return 1;
			return a.y - b.y;
		});
		const elem = matches[0];

		// Tap the element
		await adb.shell("input", "tap", String(elem.x), String(elem.y));
		await Bun.sleep(300);

		// Clear (move to end, then delete all)
		await adb.shell("input", "keyevent", "123"); // KEYCODE_MOVE_END
		await Bun.sleep(50);
		for (let i = 0; i < 20; i++) {
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

		// Type the value
		const escaped = args.value.replace(/ /g, "%s");
		await adb.shell("input", "text", escaped);
		await Bun.sleep(100);

		// Hide keyboard
		await adb.shell("input", "keyevent", "111"); // ESCAPE

		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		jsonOk({
			action: "fill",
			field: args.field,
			value: args.value,
			x: elem.x,
			y: elem.y,
			matched: elem.text || elem.contentDesc || elem.resourceId,
		});
	},
});
