import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonError, jsonOk } from "../lib/output";

export const launchCommand = defineCommand({
	meta: {
		name: "launch",
		description: "Launch an app by package name",
	},
	args: {
		package: {
			type: "positional",
			description: "Package name (e.g., com.example.app)",
			required: true,
		},
		wait: {
			type: "string",
			alias: "w",
			description: "Wait ms after launch",
		},
	},
	async run({ args }) {
		const adb = new ADB();
		await adb.getDevice();

		// Use monkey to launch the app's main activity
		const result = await adb.shellUnchecked(
			"monkey",
			"-p",
			args.package,
			"-c",
			"android.intent.category.LAUNCHER",
			"1",
		);

		if (result.stdout.includes("No activities found")) {
			jsonError(
				`No launchable activity found for package: ${args.package}`,
				"LAUNCH_FAILED",
			);
		}

		if (args.wait) {
			await Bun.sleep(Number.parseInt(args.wait, 10));
		}

		jsonOk({ action: "launch", package: args.package });
	},
});
