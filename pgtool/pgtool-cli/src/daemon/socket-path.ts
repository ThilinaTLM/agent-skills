/**
 * Cross-platform socket/pipe path resolution for the pgtool daemon.
 */

import { mkdirSync } from "node:fs";
import path from "node:path";

/**
 * Get the daemon socket path for the current platform.
 * - Linux: $XDG_RUNTIME_DIR/pgtool/daemon.sock
 * - macOS: $TMPDIR/pgtool-<uid>/daemon.sock
 * - Windows: \\.\pipe\pgtool-daemon-<username>
 */
export function getSocketPath(): string {
	if (process.platform === "win32") {
		const user = process.env.USERNAME || "unknown";
		return `\\\\.\\pipe\\pgtool-daemon-${user}`;
	}

	const dir = getSocketDir();
	return path.join(dir, "daemon.sock");
}

/**
 * Get the directory containing the daemon socket and PID file.
 * Creates the directory if it doesn't exist.
 */
export function getSocketDir(): string {
	let dir: string;

	if (process.env.XDG_RUNTIME_DIR) {
		dir = path.join(process.env.XDG_RUNTIME_DIR, "pgtool");
	} else if (process.platform === "darwin" && process.env.TMPDIR) {
		const uid = process.getuid?.() ?? "unknown";
		dir = path.join(process.env.TMPDIR, `pgtool-${uid}`);
	} else {
		const uid = process.getuid?.() ?? "unknown";
		dir = `/tmp/pgtool-${uid}`;
	}

	mkdirSync(dir, { recursive: true, mode: 0o700 });
	return dir;
}
