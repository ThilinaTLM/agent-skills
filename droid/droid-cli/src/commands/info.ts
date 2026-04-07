import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonOk } from "../lib/output";

export const infoCommand = defineCommand({
	meta: {
		name: "info",
		description: "Get device information",
	},
	async run() {
		const adb = new ADB();
		const device = await adb.getDevice();

		const [model, brand, android, sdk, screenSize, densityOutput] =
			await Promise.all([
				adb.shell("getprop", "ro.product.model"),
				adb.shell("getprop", "ro.product.brand"),
				adb.shell("getprop", "ro.build.version.release"),
				adb.shell("getprop", "ro.build.version.sdk"),
				adb.getScreenSize(),
				adb.shell("wm", "density"),
			]);

		const densityMatch = densityOutput.split(/\s+/).pop() || "0";
		const density = /^\d+$/.test(densityMatch)
			? Number.parseInt(densityMatch, 10)
			: 0;

		jsonOk({
			device,
			model,
			brand,
			android,
			sdk,
			width: screenSize.width,
			height: screenSize.height,
			density,
		});
	},
});
