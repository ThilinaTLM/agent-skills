/**
 * OS-native approval dialog for protected profiles.
 *
 * Spawns a GUI dialog that only a human can interact with —
 * the agent (which controls the terminal) cannot click GUI buttons.
 *
 * Supported platforms:
 * - Linux (X11/Wayland): zenity or kdialog
 * - macOS: osascript (AppleScript)
 * - Windows 11: PowerShell MessageBox
 */

import { execSync } from "node:child_process";

export type ApprovalResult = "approved" | "denied" | "unavailable";

export type Platform =
	| "linux-x11"
	| "linux-wayland"
	| "macos"
	| "windows"
	| "headless";

const DIALOG_TIMEOUT = 60000; // 1 minute to respond

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Request human approval for connecting to a protected profile.
 * Spawns an OS-native GUI dialog and blocks until the user responds.
 */
export async function requestApproval(
	profileName: string,
	host: string,
	database: string,
): Promise<ApprovalResult> {
	const platform = detectPlatform();

	switch (platform) {
		case "linux-x11":
		case "linux-wayland":
			return zenityApproval(profileName, host, database);
		case "macos":
			return osascriptApproval(profileName, host, database);
		case "windows":
			return powershellApproval(profileName, host, database);
		case "headless":
			return "unavailable";
	}
}

/**
 * Request human approval for a config security downgrade.
 * Shows a more detailed dialog explaining what changed.
 */
export async function requestConfigChangeApproval(
	changes: string[],
): Promise<ApprovalResult> {
	const platform = detectPlatform();
	const changeList = changes.join("\\n• ");
	const text = `Security changes detected in .pgtool.json:\\n\\n• ${changeList}\\n\\nAccept these changes?`;

	switch (platform) {
		case "linux-x11":
		case "linux-wayland":
			return zenityDialog("pgtool — Config Modified", text);
		case "macos":
			return osascriptDialog(
				"pgtool — Config Modified",
				text.replace(/\\n/g, "\n"),
			);
		case "windows":
			return powershellDialog(
				"pgtool - Config Modified",
				text.replace(/\\n/g, "`n"),
			);
		case "headless":
			return "unavailable";
	}
}

/**
 * Detect the current platform and display capabilities.
 */
export function detectPlatform(): Platform {
	if (process.platform === "win32") return "windows";
	if (process.platform === "darwin") return "macos";
	if (process.env.WAYLAND_DISPLAY) return "linux-wayland";
	if (process.env.DISPLAY) return "linux-x11";
	return "headless";
}

// ---------------------------------------------------------------------------
// Platform-specific implementations
// ---------------------------------------------------------------------------

function zenityApproval(
	profile: string,
	host: string,
	db: string,
): ApprovalResult {
	const text = `Allow connection to <b>${escapeXml(profile)}</b>?\\n\\n${escapeXml(host)}/${escapeXml(db)}`;
	return zenityDialog("pgtool — Protected Profile", text);
}

function zenityDialog(title: string, text: string): ApprovalResult {
	try {
		execSync(
			`zenity --question --title="${escapeShell(title)}" --text="${text}" --ok-label="Allow" --cancel-label="Deny" --width=400`,
			{ timeout: DIALOG_TIMEOUT, stdio: "pipe" },
		);
		return "approved";
	} catch {
		return "denied";
	}
}

function osascriptApproval(
	profile: string,
	host: string,
	db: string,
): ApprovalResult {
	const text = `Allow pgtool to connect to ${profile}?\\n\\n${host}/${db}`;
	return osascriptDialog("pgtool — Protected Profile", text);
}

function osascriptDialog(title: string, text: string): ApprovalResult {
	try {
		execSync(
			`osascript -e 'display dialog "${escapeAppleScript(text)}" with title "${escapeAppleScript(title)}" buttons {"Deny", "Allow"} default button "Deny" with icon caution'`,
			{ timeout: DIALOG_TIMEOUT, stdio: "pipe" },
		);
		return "approved";
	} catch {
		return "denied";
	}
}

function powershellApproval(
	profile: string,
	host: string,
	db: string,
): ApprovalResult {
	const text = `Allow pgtool to connect to ${profile}?\`n\`n${host}/${db}`;
	return powershellDialog("pgtool - Protected Profile", text);
}

function powershellDialog(title: string, text: string): ApprovalResult {
	try {
		const script = `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('${escapePowerShell(text)}', '${escapePowerShell(title)}', 'YesNo', 'Warning')`;
		const result = execSync(`powershell -Command "${script}"`, {
			timeout: DIALOG_TIMEOUT,
			stdio: "pipe",
			encoding: "utf-8",
		}).trim();
		return result === "Yes" ? "approved" : "denied";
	} catch {
		return "denied";
	}
}

// ---------------------------------------------------------------------------
// Escaping helpers
// ---------------------------------------------------------------------------

function escapeShell(s: string): string {
	return s.replace(/['"\\]/g, "\\$&");
}

function escapeXml(s: string): string {
	return s
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;");
}

function escapeAppleScript(s: string): string {
	return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function escapePowerShell(s: string): string {
	return s.replace(/'/g, "''");
}
