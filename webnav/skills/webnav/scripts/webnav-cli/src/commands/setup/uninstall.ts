import { existsSync, readdirSync, rmSync, unlinkSync } from "node:fs";
import { platform } from "node:os";
import { dirname } from "node:path";
import { defineCommand } from "citty";
import {
	BROWSER_SLUGS,
	getManifestPathForBrowser,
	getNativeMessagingRegistryKey,
	parseBrowserSlug,
} from "../../lib/browsers";
import { getSocketPath } from "../../lib/errors";
import { jsonError, jsonOk } from "../../lib/output";

const IS_WINDOWS = platform() === "win32";

export const uninstallCommand = defineCommand({
	meta: {
		name: "uninstall",
		description: "Remove native messaging host manifest and runtime artifacts",
	},
	args: {
		browser: {
			type: "string",
			alias: "b",
			description: `Target browser to uninstall (omit to remove all): ${BROWSER_SLUGS.join(", ")}`,
			required: false,
		},
	},
	async run({ args }) {
		const removed: string[] = [];
		const browsers: string[] = [];

		const slugsToRemove = args.browser
			? (() => {
					const slug = parseBrowserSlug(args.browser);
					if (!slug) {
						jsonError(`Unknown browser "${args.browser}"`, "INVALID_ARGS", {
							summary: `Valid browsers: ${BROWSER_SLUGS.join(", ")}`,
						});
					}
					return [slug];
				})()
			: [...BROWSER_SLUGS];

		for (const slug of slugsToRemove) {
			// Remove manifest file
			const manifestPath = getManifestPathForBrowser(slug);
			if (manifestPath && existsSync(manifestPath)) {
				unlinkSync(manifestPath);
				removed.push(manifestPath);
				browsers.push(slug);
			}

			// On Windows, also remove the registry entry
			if (IS_WINDOWS) {
				const regKey = getNativeMessagingRegistryKey(slug);
				const result = Bun.spawnSync(["reg", "delete", regKey, "/f"]);
				if (result.exitCode === 0) {
					removed.push(`registry:${regKey}`);
					if (!browsers.includes(slug)) browsers.push(slug);
				}
			}
		}

		// On Windows, clean up the manifest directory if empty
		if (IS_WINDOWS) {
			const sampleDir = dirname(getManifestPathForBrowser("chrome"));
			if (sampleDir && existsSync(sampleDir)) {
				const entries = readdirSync(sampleDir);
				if (entries.length === 0) {
					rmSync(sampleDir, { recursive: true });
					removed.push(sampleDir);
				}
			}
		}

		// On Unix, remove socket file and directory
		if (!IS_WINDOWS) {
			const socketPath = getSocketPath();
			if (existsSync(socketPath)) {
				rmSync(socketPath);
				removed.push(socketPath);
			}

			const socketDir = dirname(socketPath);
			if (existsSync(socketDir)) {
				const entries = readdirSync(socketDir);
				if (entries.length === 0) {
					rmSync(socketDir, { recursive: true });
					removed.push(socketDir);
				}
			}
		}

		jsonOk({ action: "uninstall", browsers, removed });
	},
});
