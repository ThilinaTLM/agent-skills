/**
 * Daemon client — used by CLI commands to connect to the daemon process.
 * Handles auto-starting the daemon, sending queries, and falling back to direct connections.
 */

import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import readline from "node:readline";
import type { ErrorResponse, QueryResult } from "../types";
import { isDaemonRunning } from "./pid.ts";
import type { DaemonRequest, DaemonResponse } from "./protocol.ts";
import { serialize } from "./protocol.ts";
import { getSocketPath } from "./socket-path.ts";

const CONNECT_TIMEOUT = 2000;
const QUERY_TIMEOUT = 30000;
const DAEMON_START_TIMEOUT = 3000;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Try to execute a query via the daemon.
 * Returns null if daemon is unavailable (caller should fall back to direct connection).
 */
export async function tryDaemonQuery(
	configPath: string,
	profileName: string,
	sql: string,
	params: unknown[],
	flags: { readOnly?: boolean; allowWrites?: boolean },
): Promise<{ ok: true; result: QueryResult } | ErrorResponse | null> {
	const socketPath = getSocketPath();

	try {
		const socket = await connectToSocket(socketPath, CONNECT_TIMEOUT);
		const id = randomUUID();

		const response = await sendAndReceive(
			socket,
			{
				id,
				action: "query",
				configPath,
				profile: profileName,
				sql,
				params,
				flags,
			},
			id,
			QUERY_TIMEOUT,
		);

		socket.end();
		return response as { ok: true; result: QueryResult } | ErrorResponse;
	} catch {
		return null;
	}
}

/**
 * Ensure the daemon is running. Auto-starts if needed.
 * Returns true if daemon is available, false if it couldn't be started.
 */
export async function ensureDaemon(): Promise<boolean> {
	// Check if disabled
	if (process.env.PGTOOL_NO_DAEMON === "1") return false;

	const socketPath = getSocketPath();

	// Try pinging existing daemon
	if (existsSync(socketPath) || process.platform === "win32") {
		const alive = await pingDaemon(socketPath);
		if (alive) return true;

		// Stale socket — remove it
		if (process.platform !== "win32") {
			try {
				const { unlinkSync } = await import("node:fs");
				unlinkSync(socketPath);
			} catch {
				// Ignore
			}
		}
	}

	// Start new daemon
	return startDaemon(socketPath);
}

/**
 * Send a ping to the daemon.
 */
export async function pingDaemon(socketPath?: string): Promise<boolean> {
	const sp = socketPath || getSocketPath();
	try {
		const socket = await connectToSocket(sp, CONNECT_TIMEOUT);
		const id = randomUUID();

		const response = await sendAndReceive(
			socket,
			{ id, action: "ping" },
			id,
			2000,
		);

		socket.end();
		return response?.ok === true;
	} catch {
		return false;
	}
}

/**
 * Send a status request to the daemon.
 */
export async function getDaemonStatus(): Promise<DaemonResponse | null> {
	const socketPath = getSocketPath();
	try {
		const socket = await connectToSocket(socketPath, CONNECT_TIMEOUT);
		const id = randomUUID();

		const response = await sendAndReceive(
			socket,
			{ id, action: "status" },
			id,
			2000,
		);

		socket.end();
		return response;
	} catch {
		return null;
	}
}

/**
 * Send a shutdown request to the daemon.
 */
export async function shutdownDaemon(): Promise<boolean> {
	const socketPath = getSocketPath();
	try {
		const socket = await connectToSocket(socketPath, CONNECT_TIMEOUT);
		const id = randomUUID();

		const response = await sendAndReceive(
			socket,
			{ id, action: "shutdown" },
			id,
			5000,
		);

		socket.end();
		return response?.ok === true;
	} catch {
		return false;
	}
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function connectToSocket(
	socketPath: string,
	timeout: number,
): Promise<net.Socket> {
	return new Promise((resolve, reject) => {
		const socket = net.connect({ path: socketPath }, () => {
			resolve(socket);
		});
		socket.setTimeout(timeout);
		socket.on("timeout", () => {
			socket.destroy();
			reject(new Error("Connection timeout"));
		});
		socket.on("error", reject);
	});
}

function sendAndReceive(
	socket: net.Socket,
	request: object,
	expectedId: string,
	timeout: number,
): Promise<DaemonResponse> {
	return new Promise((resolve, reject) => {
		const timer = setTimeout(() => {
			rl.close();
			reject(new Error("Response timeout"));
		}, timeout);

		const rl = readline.createInterface({ input: socket });

		rl.on("line", (line) => {
			clearTimeout(timer);
			rl.close();
			try {
				const response = JSON.parse(line) as DaemonResponse;
				if (response.id === expectedId) {
					resolve(response);
				} else {
					reject(new Error(`Unexpected response id: ${response.id}`));
				}
			} catch (e) {
				reject(e);
			}
		});

		rl.on("close", () => {
			clearTimeout(timer);
		});

		socket.write(serialize(request as DaemonRequest));
	});
}

async function startDaemon(socketPath: string): Promise<boolean> {
	const serverScript = path.join(
		path.dirname(new URL(import.meta.url).pathname),
		"server.ts",
	);

	try {
		// Detect runtime: use the same one running the CLI
		const runtime = process.argv[0];

		const args = runtime.includes("node")
			? ["--experimental-strip-types", "--no-warnings", serverScript]
			: ["run", serverScript];

		const child = spawn(runtime, args, {
			detached: true,
			stdio: "ignore",
			env: { ...process.env, PGTOOL_DAEMON: "1" },
		});

		child.unref();

		// Wait for socket to appear
		return await waitForSocket(socketPath, DAEMON_START_TIMEOUT);
	} catch {
		return false;
	}
}

function waitForSocket(socketPath: string, timeout: number): Promise<boolean> {
	return new Promise((resolve) => {
		const start = Date.now();
		const interval = setInterval(async () => {
			if (Date.now() - start > timeout) {
				clearInterval(interval);
				resolve(false);
				return;
			}

			// For named pipes on Windows, try connecting directly
			if (process.platform === "win32" || existsSync(socketPath)) {
				const alive = await pingDaemon(socketPath);
				if (alive) {
					clearInterval(interval);
					resolve(true);
				}
			}
		}, 100);
	});
}
