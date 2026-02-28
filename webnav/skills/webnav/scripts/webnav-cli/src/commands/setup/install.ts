import { existsSync, mkdirSync, unlinkSync, writeFileSync } from "node:fs";
import { platform } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineCommand } from "citty";
import {
	BROWSERS,
	BROWSER_SLUGS,
	getNativeMessagingHostsDir,
	getNativeMessagingRegistryKey,
	parseBrowserSlug,
} from "../../lib/browsers";
import {
	getInvalidExtensionIdHint,
	getMissingExtensionIdHint,
} from "../../lib/errors";
import { jsonError, jsonOk } from "../../lib/output";

const IS_WINDOWS = platform() === "win32";

function getHostWrapper(): string {
	return IS_WINDOWS ? "webnav-host.bat" : "webnav-host";
}

// Get the CLI root directory (webnav-cli/)
function getCliRoot(): string {
	const currentFile = fileURLToPath(import.meta.url);
	// Go up: commands/setup -> commands -> src -> webnav-cli
	return resolve(dirname(currentFile), "..", "..", "..");
}

export const installCommand = defineCommand({
	meta: {
		name: "install",
		description: "Install the native messaging host manifest",
	},
	args: {
		extensionId: {
			type: "positional",
			description: "Extension ID (find in your browser's extensions page)",
			required: false,
		},
		browser: {
			type: "string",
			alias: "b",
			description: `Target browser: ${BROWSER_SLUGS.join(", ")} (default: chrome)`,
			default: "chrome",
		},
	},
	async run({ args }) {
		const browserSlug = parseBrowserSlug(args.browser);
		if (!browserSlug) {
			jsonError(`Unknown browser "${args.browser}"`, "INVALID_ARGS", {
				summary: `Valid browsers: ${BROWSER_SLUGS.join(", ")}`,
			});
		}

		const browser = BROWSERS[browserSlug];
		const extensionId = args.extensionId as string;

		if (!extensionId) {
			jsonError(
				"Extension ID is required",
				"INVALID_ARGS",
				getMissingExtensionIdHint(browserSlug),
			);
		}

		// Validate extension ID format (32 lowercase letters)
		if (!/^[a-z]{32}$/.test(extensionId)) {
			jsonError(
				"Invalid extension ID format",
				"INVALID_ARGS",
				getInvalidExtensionIdHint(extensionId, browserSlug),
			);
		}

		const hostsDir = getNativeMessagingHostsDir(browserSlug);
		if (!hostsDir) {
			jsonError(`Unsupported platform: ${platform()}`, "SETUP_FAILED");
		}

		const cliRoot = getCliRoot();
		const hostWrapper = join(cliRoot, getHostWrapper());

		// Verify static host wrapper exists
		if (!existsSync(hostWrapper)) {
			jsonError(
				`Native host wrapper not found: ${hostWrapper}`,
				"SETUP_FAILED",
				"Make sure the plugin is installed correctly",
			);
		}

		// Create the manifest with correct paths
		const manifest = {
			name: "com.tlmtech.webnav",
			description: "WebNav native messaging host for browser automation",
			path: hostWrapper,
			type: "stdio",
			allowed_origins: [`chrome-extension://${extensionId}/`],
		};

		// Create directory if it doesn't exist
		if (!existsSync(hostsDir)) {
			mkdirSync(hostsDir, { recursive: true });
		}

		// Write manifest
		const manifestPath = join(hostsDir, "com.tlmtech.webnav.json");
		writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

		// On Windows, register the manifest path in the registry
		if (IS_WINDOWS) {
			const registryKey = getNativeMessagingRegistryKey(browserSlug);
			const result = Bun.spawnSync([
				"reg",
				"add",
				registryKey,
				"/ve",
				"/t",
				"REG_SZ",
				"/d",
				manifestPath,
				"/f",
			]);
			if (result.exitCode !== 0) {
				// Clean up the manifest we just wrote
				if (existsSync(manifestPath)) {
					unlinkSync(manifestPath);
				}
				jsonError(
					"Failed to create registry entry for native messaging",
					"SETUP_FAILED",
					{
						summary:
							"The registry write failed. You may need to run this command from an elevated (Administrator) prompt.",
						diagnostics: [
							`Registry key: ${registryKey}`,
							`Error: ${result.stderr.toString().trim()}`,
						],
					},
				);
			}
		}

		jsonOk({
			action: "setup",
			browser: browserSlug,
			manifest: manifestPath,
			nativeHost: hostWrapper,
			extensionId,
			hostsDir,
			hint: `Now reload the extension in ${browser.extensionsUrl} to connect`,
		});
	},
});
