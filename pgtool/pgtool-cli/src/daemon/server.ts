#!/usr/bin/env bun
/**
 * pgtool daemon server — long-lived background process that manages
 * connection pools and proxies queries over a Unix socket / named pipe.
 *
 * This file is the daemon entry point. It is spawned as a detached child process
 * by the CLI client (see client.ts).
 *
 * Security responsibilities:
 * - Reads .pgtool.json itself (CLI only sends configPath + profileName)
 * - Monitors config file integrity (hash tracking + security downgrade detection)
 * - Enforces protected profile approval via OS-native GUI dialogs
 * - Maintains protection ratchet (once protected, stays protected)
 */

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import net from "node:net";
import readline from "node:readline";
import pg from "pg";
import { loadConfig, loadFileConfig } from "../lib/config.ts";
import { mapPgError } from "../lib/connection.ts";
import type { ErrorResponse, ResolvedConnection } from "../types";
import { requestApproval } from "./approval.ts";
import {
	checkConfigIntegrity,
	isProtectedByRatchet,
} from "./config-integrity.ts";
import { removePidFile, writePidFile } from "./pid.ts";
import type {
	DaemonRequest,
	DaemonResponse,
	PoolStatus,
	QueryRequest,
} from "./protocol.ts";
import { serialize } from "./protocol.ts";
import { getSocketPath } from "./socket-path.ts";

const { Pool } = pg;

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const IDLE_TIMEOUT = 5 * 60 * 1000; // 5 minutes
const startedAt = Date.now();

// ---------------------------------------------------------------------------
// Pool management
// ---------------------------------------------------------------------------

interface ManagedPool {
	pool: pg.Pool;
	readOnly: boolean;
	queries: number;
	key: string;
}

const pools = new Map<string, ManagedPool>();

function getPoolKey(conn: ResolvedConnection): string {
	const raw =
		conn.url || `${conn.host}:${conn.port}:${conn.database}:${conn.user}`;
	// Include readOnly in key so RO and RW pools are separate
	const suffix = conn.readOnly ? ":ro" : ":rw";
	return createHash("sha256")
		.update(raw + suffix)
		.digest("hex")
		.slice(0, 16);
}

function getPoolLabel(conn: ResolvedConnection): string {
	return conn.url
		? "(url-based)"
		: `${conn.host}:${conn.port}:${conn.database}:${conn.user}`;
}

function getOrCreatePool(conn: ResolvedConnection): pg.Pool {
	const key = getPoolKey(conn);
	const existing = pools.get(key);
	if (existing) return existing.pool;

	const poolConfig: pg.PoolConfig = conn.url
		? {
				connectionString: conn.url,
				connectionTimeoutMillis: 10000,
				idleTimeoutMillis: 60000,
				max: 5,
			}
		: {
				host: conn.host,
				port: conn.port,
				database: conn.database,
				user: conn.user,
				password: conn.password,
				connectionTimeoutMillis: 10000,
				idleTimeoutMillis: 60000,
				max: 5,
			};

	if (conn.ssl !== undefined) {
		if (conn.ssl === true) {
			poolConfig.ssl = true;
		} else if (typeof conn.ssl === "object") {
			poolConfig.ssl = {
				rejectUnauthorized: conn.ssl.rejectUnauthorized,
				ca: conn.ssl.ca,
				cert: conn.ssl.cert,
				key: conn.ssl.key,
			};
		}
	}

	// Read-only enforcement via PostgreSQL connection options
	// This sets the GUC during connection handshake, before any queries
	if (conn.readOnly) {
		poolConfig.options = "-c default_transaction_read_only=on";
	}

	const pool = new Pool(poolConfig);

	pools.set(key, {
		pool,
		readOnly: conn.readOnly,
		queries: 0,
		key: getPoolLabel(conn),
	});

	return pool;
}

// ---------------------------------------------------------------------------
// Approval cache (in memory — expires when daemon exits)
// ---------------------------------------------------------------------------

const approvals = new Map<string, { approvedAt: Date }>();

function approvalKey(configPath: string, profileName: string): string {
	return `${configPath}:${profileName}`;
}

function isApproved(configPath: string, profileName: string): boolean {
	return approvals.has(approvalKey(configPath, profileName));
}

function grantApproval(configPath: string, profileName: string): void {
	approvals.set(approvalKey(configPath, profileName), {
		approvedAt: new Date(),
	});
}

// ---------------------------------------------------------------------------
// Idle timer
// ---------------------------------------------------------------------------

let idleTimer: ReturnType<typeof setTimeout>;

function resetIdleTimer(): void {
	clearTimeout(idleTimer);
	idleTimer = setTimeout(shutdown, IDLE_TIMEOUT);
}

// ---------------------------------------------------------------------------
// Request handling
// ---------------------------------------------------------------------------

async function handleRequest(
	req: DaemonRequest,
	socket: net.Socket,
): Promise<void> {
	resetIdleTimer();

	switch (req.action) {
		case "ping": {
			send(socket, { id: req.id, ok: true });
			break;
		}

		case "query": {
			await handleQuery(req, socket);
			break;
		}

		case "status": {
			const poolStatuses: PoolStatus[] = [];
			for (const [, managed] of pools) {
				poolStatuses.push({
					key: managed.key,
					active: managed.pool.totalCount - managed.pool.idleCount,
					idle: managed.pool.idleCount,
					queries: managed.queries,
					readOnly: managed.readOnly,
				});
			}

			send(socket, {
				id: req.id,
				ok: true,
				pid: process.pid,
				uptime: Math.floor((Date.now() - startedAt) / 1000),
				socket: getSocketPath(),
				pools: poolStatuses,
			});
			break;
		}

		case "shutdown": {
			send(socket, { id: req.id, ok: true });
			await shutdown();
			break;
		}
	}
}

async function handleQuery(
	req: QueryRequest,
	socket: net.Socket,
): Promise<void> {
	// -----------------------------------------------------------------------
	// Step 1: Config integrity check
	// -----------------------------------------------------------------------
	let configContent: string;
	try {
		configContent = readFileSync(req.configPath, "utf-8");
	} catch {
		send(socket, {
			id: req.id,
			ok: false,
			error: `Cannot read config file: ${req.configPath}`,
			code: "CONFIG_NOT_FOUND",
		});
		return;
	}

	// Parse the file config for integrity checking
	const fileResult = loadFileConfig(req.configPath);
	if (!fileResult.ok) {
		send(socket, { id: req.id, ...fileResult });
		return;
	}

	const integrityResult = await checkConfigIntegrity(
		req.configPath,
		configContent,
		fileResult.fileConfig,
	);

	if (integrityResult.changeRejected) {
		send(socket, {
			id: req.id,
			ok: false,
			error: "Configuration file was modified and the change was rejected",
			code: "CONFIG_TAMPERED",
			hint: "The pgtool config was modified while the daemon was running. The human rejected the changes. The daemon continues using the original configuration.",
		});
		return;
	}

	// -----------------------------------------------------------------------
	// Step 2: Resolve the profile from the (possibly cached) config
	// -----------------------------------------------------------------------
	const configResult = loadConfig(req.configPath, req.profile);
	if (!configResult.ok) {
		send(socket, { id: req.id, ...configResult });
		return;
	}

	const conn = configResult.config;

	// Apply ratchet: if profile was ever seen as protected, treat it as protected
	if (isProtectedByRatchet(req.configPath, req.profile)) {
		conn.protected = true;
	}

	// Apply CLI flag overrides (additive only: can add readOnly, can't remove protected)
	if (req.flags?.readOnly === true) {
		conn.readOnly = true;
	}
	// allowWrites only removes readOnly if profile isn't protected
	if (req.flags?.allowWrites === true && !conn.protected) {
		conn.readOnly = false;
	}

	// -----------------------------------------------------------------------
	// Step 3: Protected profile approval gate
	// -----------------------------------------------------------------------
	if (conn.protected && !isApproved(req.configPath, req.profile)) {
		const result = await requestApproval(
			conn.profileName,
			conn.host,
			conn.database,
		);

		if (result === "approved") {
			grantApproval(req.configPath, req.profile);
		} else if (result === "denied") {
			send(socket, {
				id: req.id,
				ok: false,
				error: `Connection to protected profile '${req.profile}' was denied by user`,
				code: "PROTECTED_DENIED",
				hint: "The user denied the connection request. Ask the user to approve when the dialog appears, then retry this command.",
			});
			return;
		} else {
			// unavailable — no display
			send(socket, {
				id: req.id,
				ok: false,
				error: `Cannot approve protected profile '${req.profile}': no display available`,
				code: "PROTECTED_DENIED",
				hint: "Protected profiles require a desktop environment for the approval dialog. Ask the user to run this command from a machine with a display.",
			});
			return;
		}
	}

	// -----------------------------------------------------------------------
	// Step 4: Execute query
	// -----------------------------------------------------------------------
	const pool = getOrCreatePool(conn);
	const key = getPoolKey(conn);

	try {
		const result = await pool.query(req.sql, req.params);
		const managed = pools.get(key);
		if (managed) managed.queries++;

		send(socket, {
			id: req.id,
			ok: true,
			result: {
				rows: result.rows,
				rowCount: result.rowCount ?? result.rows.length,
				fields: result.fields.map((f) => ({
					name: f.name,
					dataTypeID: f.dataTypeID,
				})),
			},
		});
	} catch (e) {
		const error = mapPgError(e as Error & { code?: string });
		send(socket, { id: req.id, ...error });
	}
}

// ---------------------------------------------------------------------------
// Socket communication
// ---------------------------------------------------------------------------

function send(socket: net.Socket, msg: DaemonResponse): void {
	try {
		socket.write(serialize(msg));
	} catch {
		// Client disconnected
	}
}

// ---------------------------------------------------------------------------
// Server lifecycle
// ---------------------------------------------------------------------------

const socketPath = getSocketPath();

// Clean up stale socket file
try {
	const { unlinkSync } = await import("node:fs");
	unlinkSync(socketPath);
} catch {
	// File didn't exist, that's fine
}

const server = net.createServer((socket) => {
	const rl = readline.createInterface({ input: socket });

	rl.on("line", async (line) => {
		try {
			const req = JSON.parse(line) as DaemonRequest;
			await handleRequest(req, socket);
		} catch (e) {
			const errorMsg: ErrorResponse = {
				ok: false,
				error: `Invalid request: ${e instanceof Error ? e.message : String(e)}`,
				code: "QUERY_FAILED",
			};
			send(socket, { id: "unknown", ...errorMsg });
		}
	});

	rl.on("close", () => {
		socket.destroy();
	});

	socket.on("error", () => {
		// Client disconnected unexpectedly, ignore
	});
});

server.listen(socketPath, () => {
	writePidFile();
	resetIdleTimer();
});

server.on("error", (err) => {
	console.error(`Daemon server error: ${err.message}`);
	process.exit(1);
});

async function shutdown(): Promise<void> {
	clearTimeout(idleTimer);

	// Close all pools
	const closePromises: Promise<void>[] = [];
	for (const [, managed] of pools) {
		closePromises.push(managed.pool.end());
	}
	await Promise.allSettled(closePromises);
	pools.clear();

	// Close server
	server.close();

	// Clean up files
	removePidFile();
	try {
		const { unlinkSync } = await import("node:fs");
		unlinkSync(socketPath);
	} catch {
		// Already removed
	}

	process.exit(0);
}

// Handle signals
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
