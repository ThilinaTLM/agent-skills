/**
 * PID file management for the daemon process.
 */

import { existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import path from "node:path";
import { getSocketDir } from "./socket-path.ts";

const PID_FILENAME = "daemon.pid";

/**
 * Get the path to the PID file.
 */
export function getPidPath(): string {
	return path.join(getSocketDir(), PID_FILENAME);
}

/**
 * Write the current process PID to the PID file.
 */
export function writePidFile(): void {
	writeFileSync(getPidPath(), String(process.pid), "utf-8");
}

/**
 * Read the PID from the PID file.
 * Returns null if the file doesn't exist or can't be read.
 */
export function readPidFile(): number | null {
	try {
		const pidPath = getPidPath();
		if (!existsSync(pidPath)) return null;
		const content = readFileSync(pidPath, "utf-8").trim();
		const pid = Number.parseInt(content, 10);
		return Number.isNaN(pid) ? null : pid;
	} catch {
		return null;
	}
}

/**
 * Remove the PID file.
 */
export function removePidFile(): void {
	try {
		const pidPath = getPidPath();
		if (existsSync(pidPath)) {
			unlinkSync(pidPath);
		}
	} catch {
		// Ignore cleanup errors
	}
}

/**
 * Check if a process with the given PID is running.
 */
export function isProcessRunning(pid: number): boolean {
	try {
		process.kill(pid, 0);
		return true;
	} catch {
		return false;
	}
}

/**
 * Check if the daemon appears to be running (PID file exists + process alive).
 */
export function isDaemonRunning(): { running: boolean; pid: number | null } {
	const pid = readPidFile();
	if (pid === null) return { running: false, pid: null };
	if (!isProcessRunning(pid)) {
		// Stale PID file
		removePidFile();
		return { running: false, pid: null };
	}
	return { running: true, pid };
}
