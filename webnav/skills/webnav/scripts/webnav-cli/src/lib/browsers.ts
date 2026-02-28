/**
 * Browser registry — single source of truth for supported browsers.
 */

import { existsSync } from "node:fs";
import { homedir, platform } from "node:os";
import { join } from "node:path";

export type BrowserSlug = "chrome" | "brave" | "edge" | "chromium";

export const BROWSER_SLUGS: BrowserSlug[] = [
	"chrome",
	"brave",
	"edge",
	"chromium",
];

const MANIFEST_FILENAME = "com.tlmtech.webnav.json";

interface BrowserMeta {
	name: string;
	extensionsUrl: string;
	paths: {
		darwin: string[];
		linux: string[];
		win32: string;
	};
}

export const BROWSERS: Record<BrowserSlug, BrowserMeta> = {
	chrome: {
		name: "Chrome",
		extensionsUrl: "chrome://extensions",
		paths: {
			darwin: ["Google", "Chrome"],
			linux: ["google-chrome"],
			win32: "Google\\Chrome",
		},
	},
	brave: {
		name: "Brave",
		extensionsUrl: "brave://extensions",
		paths: {
			darwin: ["BraveSoftware", "Brave-Browser"],
			linux: ["BraveSoftware", "Brave-Browser"],
			win32: "BraveSoftware\\Brave-Browser",
		},
	},
	edge: {
		name: "Edge",
		extensionsUrl: "edge://extensions",
		paths: {
			darwin: ["Microsoft Edge"],
			linux: ["microsoft-edge"],
			win32: "Microsoft\\Edge",
		},
	},
	chromium: {
		name: "Chromium",
		extensionsUrl: "chrome://extensions",
		paths: {
			darwin: ["Chromium"],
			linux: ["chromium"],
			win32: "Chromium",
		},
	},
};

/**
 * Resolve the NativeMessagingHosts directory for a given browser + platform.
 * On Windows, manifests go to a shared per-user directory (registry points to them).
 */
export function getNativeMessagingHostsDir(browser: BrowserSlug): string {
	const os = platform();
	const meta = BROWSERS[browser];

	if (os === "darwin") {
		return join(
			homedir(),
			"Library",
			"Application Support",
			...meta.paths.darwin,
			"NativeMessagingHosts",
		);
	}
	if (os === "linux") {
		return join(
			homedir(),
			".config",
			...meta.paths.linux,
			"NativeMessagingHosts",
		);
	}
	if (os === "win32") {
		const localAppData =
			process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local");
		return join(localAppData, "WebNav", "NativeMessagingHosts");
	}

	return "";
}

/**
 * Return the Windows registry key for a browser's native messaging host.
 */
export function getNativeMessagingRegistryKey(browser: BrowserSlug): string {
	const meta = BROWSERS[browser];
	return `HKCU\\Software\\${meta.paths.win32}\\NativeMessagingHosts\\com.tlmtech.webnav`;
}

/**
 * Full manifest file path for a given browser.
 */
export function getManifestPathForBrowser(browser: BrowserSlug): string {
	const dir = getNativeMessagingHostsDir(browser);
	if (!dir) return "";
	return join(dir, MANIFEST_FILENAME);
}

/**
 * Validate and parse a string into a BrowserSlug, or return undefined.
 */
export function parseBrowserSlug(value: string): BrowserSlug | undefined {
	if (BROWSER_SLUGS.includes(value as BrowserSlug)) {
		return value as BrowserSlug;
	}
	return undefined;
}

/**
 * Return the list of browsers that currently have a manifest installed.
 * On Windows, checks both the manifest file and registry entry.
 */
export function getInstalledBrowsers(): BrowserSlug[] {
	if (platform() === "win32") {
		return BROWSER_SLUGS.filter((slug) => {
			const p = getManifestPathForBrowser(slug);
			if (!p || !existsSync(p)) return false;
			const regKey = getNativeMessagingRegistryKey(slug);
			const result = Bun.spawnSync(["reg", "query", regKey, "/ve"]);
			return result.exitCode === 0;
		});
	}
	return BROWSER_SLUGS.filter((slug) => {
		const p = getManifestPathForBrowser(slug);
		return p !== "" && existsSync(p);
	});
}
