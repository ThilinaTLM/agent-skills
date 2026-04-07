import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonError, jsonOk } from "../lib/output";

export const swipeCommand = defineCommand({
	meta: {
		name: "swipe",
		description: "Swipe gesture for scrolling",
	},
	args: {
		direction: {
			type: "positional",
			description: "Swipe direction: up, down, left, right",
			required: true,
		},
		duration: {
			type: "string",
			alias: "d",
			default: "300",
			description: "Swipe duration in ms",
		},
		wait: {
			type: "string",
			alias: "w",
			description: "Wait ms after swipe",
		},
	},
	async run({ args }) {
		const adb = new ADB();
		await adb.getDevice();

		const { width, height } = await adb.getScreenSize();
		const cx = Math.floor(width / 2);
		const cy = Math.floor(height / 2);
		const duration = args.duration;

		let startX: number;
		let startY: number;
		let endX: number;
		let endY: number;

		const direction = args.direction.toLowerCase();
		switch (direction) {
			case "up":
				startX = cx;
				startY = Math.floor((height * 3) / 4);
				endX = cx;
				endY = Math.floor(height / 4);
				break;
			case "down":
				startX = cx;
				startY = Math.floor(height / 4);
				endX = cx;
				endY = Math.floor((height * 3) / 4);
				break;
			case "left":
				startX = Math.floor((width * 3) / 4);
				startY = cy;
				endX = Math.floor(width / 4);
				endY = cy;
				break;
			case "right":
				startX = Math.floor(width / 4);
				startY = cy;
				endX = Math.floor((width * 3) / 4);
				endY = cy;
				break;
			default:
				jsonError(`Invalid direction: ${direction}`, "INVALID_DIRECTION");
		}

		await adb.shell(
			"input",
			"swipe",
			String(startX),
			String(startY),
			String(endX),
			String(endY),
			duration,
		);

		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		jsonOk({ action: "swipe", direction });
	},
});
