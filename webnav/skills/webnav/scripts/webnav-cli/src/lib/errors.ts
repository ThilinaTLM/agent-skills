/**
 * Centralized error hints for self-documenting CLI errors.
 * Provides structured hints that AI can parse to guide users through setup/troubleshooting.
 */

import { existsSync } from "node:fs";
import { homedir, platform } from "node:os";
import { join, resolve } from "node:path";
import type { ErrorCode, ErrorHint } from "../types";
import {
	BROWSERS,
	type BrowserSlug,
	getInstalledBrowsers,
	getManifestPathForBrowser,
} from "./browsers";

const IS_WINDOWS = platform() === "win32";
const SOCKET_PATH = IS_WINDOWS
	? "\\\\.\\pipe\\webnav"
	: join(homedir(), ".webnav", "webnav.sock");
const EXTENSION_DIST_PATH = resolve(
	import.meta.dir,
	"../../../../extension/dist",
);

// ── Internal helpers ────────────────────────────────────────────────

function browserLabel(browser?: BrowserSlug): string {
	return browser ? BROWSERS[browser].name : "your browser";
}

function extensionsUrl(browser?: BrowserSlug): string {
	if (browser) return BROWSERS[browser].extensionsUrl;
	// Try to detect from installed manifests
	const installed = getInstalledBrowsers();
	if (installed.length === 1) return BROWSERS[installed[0]].extensionsUrl;
	return "chrome://extensions";
}

// ── Reusable context fragments ──────────────────────────────────────

function askForIdContext(): string {
	return `[ASK USER] Ask the user for BOTH of the following (the AI CANNOT see these, the user MUST provide them):
   - The 32-character extension ID shown on the extension card
   - Which browser they installed it in (chrome, brave, edge, chromium)
   - Do NOT proceed until the user provides both values`;
}

function freshInstallContext(extUrl: string): string {
	return [
		`[USER action] Tell the user to open extensions page (${extUrl}), enable 'Developer mode', click 'Load unpacked' and select: ${EXTENSION_DIST_PATH}`,
		askForIdContext(),
		"[AI runs] Run: webnav setup install <extension-id> --browser <browser>",
		"[USER action] Ask the user to reload the extension (click reload icon on extensions page)",
		"[AI runs] Run: webnav status — to verify the connection",
	].join("\n");
}

function reinstallContext(extUrl: string): string {
	return [
		`[USER action] Tell the user to remove the old WebNav from the extensions page (${extUrl}), then click 'Load unpacked' and select: ${EXTENSION_DIST_PATH}`,
		askForIdContext(),
		"[AI runs] Run: webnav setup install <extension-id> --browser <browser>",
		"[AI runs] Run: webnav status — to verify the connection",
	].join("\n");
}

function reloadAndVerifyContext(): string {
	return `[USER action] Ask the user to reload the extension (click reload icon on extensions page)
[AI runs] Run: webnav status — to verify the connection`;
}

// ── Public path / state helpers ─────────────────────────────────────

/**
 * Get the native messaging manifest path.
 * If a browser is specified, returns its path. Otherwise returns the first
 * installed browser's path, falling back to Chrome.
 */
export function getManifestPath(browser?: BrowserSlug): string {
	if (browser) return getManifestPathForBrowser(browser);

	const installed = getInstalledBrowsers();
	if (installed.length > 0) return getManifestPathForBrowser(installed[0]);
	return getManifestPathForBrowser("chrome");
}

/**
 * Check if any browser has a native messaging manifest installed.
 */
export function manifestExists(): boolean {
	return getInstalledBrowsers().length > 0;
}

/**
 * Check if the IPC endpoint exists (indicates native host is running).
 * On Windows, named pipes don't exist on the filesystem — we skip the check
 * and let the connection attempt determine availability.
 */
export function socketExists(): boolean {
	if (IS_WINDOWS) return true;
	return existsSync(SOCKET_PATH);
}

/**
 * Get the socket path.
 */
export function getSocketPath(): string {
	return SOCKET_PATH;
}

// ── Connection error detection ──────────────────────────────────────

/**
 * Detect connection state and return appropriate error code and hint.
 */
export function getConnectionErrorHint(): { code: ErrorCode; hint: ErrorHint } {
	const hasManifest = manifestExists();
	const hasSocket = socketExists();

	if (!hasManifest) {
		return {
			code: "SETUP_REQUIRED",
			hint: getSetupRequiredHint(),
		};
	}

	if (!hasSocket) {
		return {
			code: "NOT_CONNECTED",
			hint: getNotConnectedHint(),
		};
	}

	// Socket exists but connection failed - likely stale
	return {
		code: "CONNECTION_FAILED",
		hint: getConnectionFailedHint(),
	};
}

// ── Hint functions ──────────────────────────────────────────────────

/**
 * Full setup instructions for fresh systems.
 */
export function getSetupRequiredHint(browser?: BrowserSlug): ErrorHint {
	const label = browserLabel(browser);
	const extUrl = extensionsUrl(browser);

	return {
		summary: `WebNav has not been set up. Complete the one-time setup to connect ${label} to the CLI.`,
		steps: [
			"Step 1: Load the extension",
			`  - Open ${label}: ${extUrl}`,
			"  - Enable 'Developer mode' (top-right toggle)",
			"  - Click 'Load unpacked'",
			`  - Select: ${EXTENSION_DIST_PATH}`,
			"",
			"Step 2: Copy the Extension ID",
			`  - Find WebNav card in ${extUrl}`,
			"  - Copy the 32-character ID under the name",
			"",
			"Step 3: Run setup",
			browser
				? `  - Run: webnav setup install <your-id> --browser ${browser}`
				: "  - Run: webnav setup install <your-id>",
			"",
			"Step 4: Reload extension",
			`  - Click reload icon on WebNav card in ${extUrl}`,
			"",
			"Step 5: Verify",
			"  - Run: webnav status",
		],
		diagnostics: IS_WINDOWS
			? [
					'Check registry: reg query "HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\com.tlmtech.webnav" /ve',
					`Check manifest: dir "${process.env.LOCALAPPDATA || ""}\\WebNav\\NativeMessagingHosts\\"`,
				]
			: [
					"Check manifest: ls -la ~/.config/*/NativeMessagingHosts/ ~/Library/Application\\ Support/*/NativeMessagingHosts/ 2>/dev/null",
					"Check socket: ls -la ~/.webnav/",
				],
		context: `SETUP_REQUIRED: The AI agent MUST guide the user through setup. Do NOT skip any step.\n\n${freshInstallContext(extUrl)}`,
	};
}

/**
 * Hint when manifest exists but socket doesn't (extension not loaded/connected).
 */
export function getNotConnectedHint(browser?: BrowserSlug): ErrorHint {
	const label = browserLabel(browser);
	const extUrl = extensionsUrl(browser);
	const distExists = existsSync(EXTENSION_DIST_PATH);

	return {
		summary: `WebNav is set up but the extension is not connected. This could mean the extension is not installed in ${label} or ${label} is not running.`,
		steps: [
			"If the extension is NOT installed in the browser:",
			"  Step 1: Load the extension",
			`    - Open ${label}: ${extUrl}`,
			"    - Enable 'Developer mode' (top-right toggle)",
			"    - Click 'Load unpacked'",
			`    - Select: ${EXTENSION_DIST_PATH}`,
			"  Step 2: Copy the Extension ID",
			"    - Find WebNav card on the extensions page",
			"    - Copy the 32-character ID under the name",
			"  Step 3: Run setup",
			"    - Run: webnav setup install <your-id>",
			"  Step 4: Reload extension",
			`    - Click reload icon on WebNav card in ${extUrl}`,
			"  Step 5: Verify",
			"    - Run: webnav status",
			"",
			"If the extension IS installed but not connected:",
			`  Step 1: Check ${label} is running`,
			`    - Open ${label} if not already running`,
			"  Step 2: Reload the extension",
			`    - Open ${label}: ${extUrl}`,
			"    - Find WebNav and click the reload icon",
			"  Step 3: Verify connection",
			"    - Run: webnav status",
			"  If still not connected:",
			"    - The extension may be loaded from an outdated path",
			"    - Remove WebNav from extensions page",
			`    - Load unpacked from: ${EXTENSION_DIST_PATH}`,
			"    - Copy the new extension ID and run: webnav setup install <new-id>",
			"    - Run: webnav status",
		],
		diagnostics: [
			...(IS_WINDOWS
				? [
						`Check registry: reg query "HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\com.tlmtech.webnav" /ve`,
					]
				: ["Check socket: ls -la ~/.webnav/"]),
			`Check extension errors: ${label} > ${extUrl} > WebNav > Errors`,
			...(IS_WINDOWS
				? [`Check extension dist exists: dir "${EXTENSION_DIST_PATH}"`]
				: [`Check extension dist exists: ls -la ${EXTENSION_DIST_PATH}`]),
			...(distExists
				? []
				: [
						`WARNING: Extension dist directory not found at ${EXTENSION_DIST_PATH}. Run 'bun run build' in the extension directory first.`,
					]),
		],
		context: `NOT_CONNECTED: The native messaging manifest exists but the extension is not connected.\n\n[ASK USER] Ask: 'Is the WebNav extension installed and visible in your browser extensions page?'\n\nIf NOT installed:\n${freshInstallContext(extUrl)}\n\nIf IS installed:\n${reloadAndVerifyContext()}\nIf still not connected — the extension may be loaded from an outdated path (e.g. after a plugin update). Full reinstall:\n${reinstallContext(extUrl)}`,
	};
}

/**
 * Hint when socket exists but connection fails (stale socket, native host crashed).
 */
export function getConnectionFailedHint(browser?: BrowserSlug): ErrorHint {
	const label = browserLabel(browser);
	const extUrl = extensionsUrl(browser);

	if (IS_WINDOWS) {
		return {
			summary:
				"Connection to WebNav failed. The native host may not be running or the extension is not connected.",
			steps: [
				"Step 1: Reload the extension",
				`  - Open ${label}: ${extUrl}`,
				"  - Find WebNav and click the reload icon",
				"",
				"Step 2: Verify connection",
				"  - Run: webnav status",
			],
			diagnostics: [
				`Check if ${label} is running: Get-Process chrome -ErrorAction SilentlyContinue`,
				`Check registry: reg query "HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\com.tlmtech.webnav" /ve`,
			],
			context: `CONNECTION_FAILED: The native host is not responding.\n\n${reloadAndVerifyContext()}\n\nIf webnav status still fails — the extension may be from an outdated path. Full reinstall:\n${reinstallContext(extUrl)}`,
		};
	}

	return {
		summary:
			"Connection to WebNav failed. The socket exists but the native host may have crashed or the socket is stale.",
		steps: [
			"Step 1: Remove stale socket",
			"  - Run: rm ~/.webnav/webnav.sock",
			"",
			"Step 2: Reload the extension",
			`  - Open ${label}: ${extUrl}`,
			"  - Find WebNav and click the reload icon",
			"",
			"Step 3: Verify connection",
			"  - Run: webnav status",
		],
		diagnostics: [
			"Check socket: ls -la ~/.webnav/",
			`Check if ${label} is running: pgrep -x chrome || pgrep -x 'Google Chrome'`,
		],
		context: `CONNECTION_FAILED: The socket file exists but the native host is not responding (likely stale).\n\n[AI runs] Run: rm ~/.webnav/webnav.sock\n${reloadAndVerifyContext()}\n\nIf webnav status still fails — the extension may be from an outdated path. Full reinstall:\n${reinstallContext(extUrl)}`,
	};
}

/**
 * Hint when connected but extension doesn't respond.
 */
export function getExtensionDisconnectedHint(browser?: BrowserSlug): ErrorHint {
	const label = browserLabel(browser);
	const extUrl = extensionsUrl(browser);

	return {
		summary:
			"The native host is running but the extension is not responding. The extension may be disabled or unresponsive.",
		steps: [
			"Step 1: Check extension status",
			`  - Open ${label}: ${extUrl}`,
			"  - Verify WebNav is enabled (toggle should be on)",
			"",
			"Step 2: Reload the extension",
			"  - Click the reload icon on WebNav card",
			"",
			"Step 3: Check for errors",
			"  - Click 'Errors' on the WebNav card if visible",
			`  - Open ${label} DevTools (F12) > Console for extension errors`,
			"",
			"Step 4: Verify connection",
			"  - Run: webnav status",
		],
		diagnostics: [
			"Check native host logs: webnav native-host (run manually to see stderr)",
			...(IS_WINDOWS ? [] : ["Check socket: ls -la ~/.webnav/"]),
		],
		context: `EXTENSION_DISCONNECTED: The native host is running but the extension is not responding.\n\n[USER action] Ask the user to check that WebNav is enabled on the extensions page (${extUrl})\n${reloadAndVerifyContext()}\n\nIf still not responding after reload, the extension may need a full reinstall:\n${reinstallContext(extUrl)}`,
	};
}

/**
 * Hint for timeout errors.
 */
export function getTimeoutHint(timeoutMs: number): ErrorHint {
	return {
		summary: `Command timed out after ${timeoutMs}ms. The page may be loading slowly or the extension is unresponsive.`,
		steps: [
			"Step 1: Check if page is still loading",
			"  - Wait for the page to finish loading",
			"  - Retry the command",
			"",
			"Step 2: If page is loaded, reload extension",
			`  - Open ${extensionsUrl()}`,
			"  - Click reload icon on WebNav card",
			"",
			"Step 3: Retry the command",
			"  - Run your command again",
		],
		diagnostics: ["Check extension status: webnav status"],
		context: `TIMEOUT: Command timed out after ${timeoutMs}ms.\n\n[AI runs] Wait a moment, then retry the command.\nIf the command still times out:\n${reloadAndVerifyContext()}`,
	};
}

/**
 * Hint when extension version doesn't match CLI version.
 */
export function getExtensionOutdatedHint(
	extensionVersion: string,
	cliVersion: string,
): ErrorHint {
	const extUrl = extensionsUrl();
	return {
		summary: `BLOCKING: Extension version (${extensionVersion}) does not match CLI version (${cliVersion}). WebNav cannot be used until the extension is reinstalled. Do NOT run any other webnav commands until this is resolved.`,
		steps: [
			"Step 1: Remove the old extension",
			`  - Open: ${extUrl}`,
			"  - Find WebNav and click 'Remove'",
			"",
			"Step 2: Load the new extension",
			`  - On the same page (${extUrl}), click 'Load unpacked'`,
			`  - Select: ${EXTENSION_DIST_PATH}`,
			"",
			"Step 3: Copy the new extension ID",
			"  - Find the new WebNav card",
			"  - Copy the 32-character ID under the name",
			"",
			"Step 4: Run setup with the new ID",
			"  - Run: webnav setup install <new-id>",
			"",
			"Step 5: Verify",
			"  - Run: webnav status",
		],
		context: `EXTENSION_OUTDATED — STOP: Do NOT run any other webnav commands. This version mismatch MUST be resolved first.

CLI version: ${cliVersion}, Extension version: ${extensionVersion}.
A simple reload is NOT sufficient — after a plugin update the extension path changes, so the old extension must be fully removed and reinstalled. Commands will produce unreliable results until versions match.

[AI AGENT INSTRUCTIONS] You MUST stop and guide the user through the reinstall below. Do NOT skip this, do NOT retry commands, do NOT proceed with any browser automation until webnav status succeeds without error.

${reinstallContext(extUrl)}`,
	};
}

/**
 * Hint for invalid extension ID format.
 */
export function getInvalidExtensionIdHint(
	providedId: string,
	browser?: BrowserSlug,
): ErrorHint {
	const extUrl = extensionsUrl(browser);
	const issues: string[] = [];
	if (providedId.length !== 32) {
		issues.push(`Got ${providedId.length} characters, expected 32`);
	}
	if (/[A-Z]/.test(providedId)) {
		issues.push("Contains uppercase letters (should be lowercase only)");
	}
	if (/[^a-zA-Z]/.test(providedId)) {
		issues.push("Contains non-letter characters (should be letters a-z only)");
	}

	return {
		summary:
			"Invalid extension ID format. Extension IDs are exactly 32 lowercase letters.",
		steps: [
			"Step 1: Open extensions page",
			`  - Navigate to: ${extUrl}`,
			"",
			"Step 2: Find WebNav extension",
			"  - Look for the WebNav card",
			"  - The ID is the 32-character string under the extension name",
			"",
			"Step 3: Copy carefully",
			"  - Select and copy the entire ID",
			"  - Make sure no extra spaces or characters are included",
			"",
			"Step 4: Run setup again",
			browser
				? `  - Run: webnav setup install <your-id> --browser ${browser}`
				: "  - Run: webnav setup install <your-id>",
		],
		context: `INVALID_EXTENSION_ID: The provided extension ID is not valid.${issues.length > 0 ? ` ${issues.join("; ")}.` : ""}\n\n[ASK USER] Tell the user the ID was invalid and ask them to:\n   - Open the extensions page (${extUrl})\n   - Find the WebNav card and carefully copy the 32-character ID (lowercase letters only, no spaces)\n   - Provide the correct ID\n   - Do NOT proceed until the user provides a valid ID\n\n[AI runs] Run: webnav setup install <correct-id> --browser <browser>`,
	};
}

/**
 * Hint for missing extension ID argument.
 */
export function getMissingExtensionIdHint(browser?: BrowserSlug): ErrorHint {
	const extUrl = extensionsUrl(browser);

	return {
		summary: "Extension ID is required to configure native messaging.",
		steps: [
			"Step 1: Find your extension ID",
			`  - Open: ${extUrl}`,
			"  - Find WebNav card",
			"  - Copy the 32-character ID under the name",
			"",
			"Step 2: Run setup with the ID",
			browser
				? `  - Run: webnav setup install <your-id> --browser ${browser}`
				: "  - Run: webnav setup install <your-id>",
		],
		context: `MISSING_EXTENSION_ID: The setup install command requires an extension ID. If the extension is not yet loaded in the browser, tell the user to load it from: ${EXTENSION_DIST_PATH}\n\n${askForIdContext()}\n\n[AI runs] Run: webnav setup install <extension-id> --browser <browser>`,
	};
}
