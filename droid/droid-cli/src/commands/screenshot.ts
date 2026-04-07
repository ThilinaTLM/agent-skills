import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonOk } from "../lib/output";
import { dumpUIHierarchy } from "../lib/ui-hierarchy";

export const screenshotCommand = defineCommand({
	meta: {
		name: "screenshot",
		description: "Capture screenshot and UI elements",
	},
	args: {
		clickable: {
			type: "boolean",
			alias: "c",
			description: "Only return clickable elements",
		},
		text: {
			type: "string",
			alias: "t",
			description: "Filter elements by text",
		},
		dir: {
			type: "string",
			alias: "d",
			description: "Output directory (default: system temp)",
		},
		"no-ui": {
			type: "boolean",
			description: "Skip UI hierarchy dump (faster)",
		},
	},
	async run({ args }) {
		const adb = new ADB();
		await adb.getDevice();

		const outputDir = args.dir || os.tmpdir();
		if (!fs.existsSync(outputDir)) {
			fs.mkdirSync(outputDir, { recursive: true });
		}

		// Take screenshot
		const timestamp = new Date()
			.toISOString()
			.replace(/[:-]/g, "")
			.replace("T", "_")
			.slice(0, 15);
		const screenshotFile = path.join(outputDir, `screenshot_${timestamp}.png`);
		const remoteScreenshot = "/sdcard/screenshot.png";

		await adb.shell("screencap", "-p", remoteScreenshot);
		await adb.pull(remoteScreenshot, screenshotFile);
		await adb.shellUnchecked("rm", remoteScreenshot);

		// Dump UI hierarchy (skip if --no-ui)
		let elements = args["no-ui"] ? [] : await dumpUIHierarchy(adb);

		// Apply filters
		if (args.clickable) {
			elements = elements.filter((e) => e.clickable);
		}

		if (args.text) {
			elements = elements.filter((e) => e.matches(args.text as string));
		}

		jsonOk({
			screenshot: screenshotFile,
			elements: elements.map((e) => e.toDict()),
		});
	},
});
