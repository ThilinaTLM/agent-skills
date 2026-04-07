import { defineCommand } from "citty";
import { ADB } from "../lib/adb";
import { jsonError, jsonOk } from "../lib/output";

export const currentCommand = defineCommand({
	meta: {
		name: "current",
		description: "Get the currently visible activity",
	},
	async run() {
		const adb = new ADB();
		await adb.getDevice();

		// Get the resumed activity from dumpsys
		const output = await adb.shell("dumpsys", "activity", "activities");

		// Parse mResumedActivity line
		let activity: string | null = null;
		let packageName: string | null = null;

		for (const line of output.split("\n")) {
			if (
				line.includes("mResumedActivity") ||
				line.includes("topResumedActivity")
			) {
				// Format: mResumedActivity: ActivityRecord{...  com.example.app/.MainActivity ...}
				const match = line.match(/(\S+)\/(\S+)/);
				if (match) {
					packageName = match[1];
					const activityName = match[2];
					activity = `${packageName}/${activityName}`;
					break;
				}
			}
		}

		if (!activity || !packageName) {
			jsonError("Could not determine current activity", "ACTIVITY_NOT_FOUND");
		}

		jsonOk({ action: "current", activity, package: packageName });
	},
});
