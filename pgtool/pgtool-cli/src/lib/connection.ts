import pg from "pg";
import { ensureDaemon, tryDaemonQuery } from "../daemon/client.ts";
import type { ErrorResponse, QueryResult, ResolvedConnection } from "../types";

const { Pool } = pg;

let pool: pg.Pool | null = null;
let currentProfileName: string | null = null;

// Daemon routing context
let daemonConfigPath: string | null = null;
let daemonProfileName: string | null = null;
let daemonFlags: { readOnly?: boolean; allowWrites?: boolean } = {};
let daemonReady = false;

/**
 * Set the daemon context for routing queries through the daemon.
 */
export function setDaemonContext(
	configPath: string,
	profileName: string,
	flags: { readOnly?: boolean; allowWrites?: boolean },
): void {
	daemonConfigPath = configPath;
	daemonProfileName = profileName;
	daemonFlags = flags;
}

/**
 * Initialize the daemon connection (auto-start if needed).
 */
export async function initDaemon(): Promise<void> {
	if (daemonConfigPath) {
		daemonReady = await ensureDaemon();
	}
}

/**
 * Initialize the database connection pool.
 */
export function initConnection(config: ResolvedConnection): void {
	if (pool) {
		return;
	}

	currentProfileName = config.profileName;

	const poolConfig: pg.PoolConfig = config.url
		? {
				connectionString: config.url,
				connectionTimeoutMillis: 10000,
				idleTimeoutMillis: 30000,
				max: 5,
			}
		: {
				host: config.host,
				port: config.port || 5432,
				database: config.database,
				user: config.user,
				password: config.password,
				connectionTimeoutMillis: 10000,
				idleTimeoutMillis: 30000,
				max: 5,
			};

	// SSL configuration
	if (config.ssl !== undefined) {
		if (config.ssl === true) {
			poolConfig.ssl = true;
		} else if (typeof config.ssl === "object") {
			poolConfig.ssl = {
				rejectUnauthorized: config.ssl.rejectUnauthorized,
				ca: config.ssl.ca,
				cert: config.ssl.cert,
				key: config.ssl.key,
			};
		}
	}

	// Read-only enforcement via PostgreSQL connection options
	// This sets the GUC during connection handshake, before any queries
	if (config.readOnly) {
		poolConfig.options = "-c default_transaction_read_only=on";
	}

	pool = new Pool(poolConfig);
}

/**
 * Close the database connection pool.
 */
export async function closeConnection(): Promise<void> {
	if (pool) {
		await pool.end();
		pool = null;
		currentProfileName = null;
	}
}

/**
 * Execute a parameterized query.
 * @param sql - SQL query with $1, $2, etc. placeholders
 * @param params - Parameter values
 * @returns Query result or error response
 */
export async function query<T extends Record<string, unknown>>(
	sql: string,
	params: unknown[] = [],
): Promise<{ ok: true; result: QueryResult } | ErrorResponse> {
	// Try daemon first
	if (daemonReady && daemonConfigPath && daemonProfileName) {
		const daemonResult = await tryDaemonQuery(
			daemonConfigPath,
			daemonProfileName,
			sql,
			params,
			daemonFlags,
		);
		if (daemonResult) return daemonResult;
		// Daemon failed — fall through to direct connection
	}

	// Direct connection fallback
	if (!pool) {
		return {
			ok: false,
			error: "Database connection not initialized",
			code: "CONNECTION_FAILED",
			hint: "Ensure loadConfig and initConnection are called before querying",
		};
	}

	try {
		const result = await pool.query(sql, params);

		return {
			ok: true,
			result: {
				rows: result.rows as T[],
				rowCount: result.rowCount ?? result.rows.length,
				fields: result.fields.map((f) => ({
					name: f.name,
					dataTypeID: f.dataTypeID,
				})),
			},
		};
	} catch (e) {
		const error = e as Error & { code?: string };
		return mapPgError(error);
	}
}

/**
 * Map a PostgreSQL error to our error response format.
 */
export function mapPgError(error: Error & { code?: string }): ErrorResponse {
	// Read-only transaction violation
	if (error.code === "25006") {
		const profileHint = currentProfileName
			? ` Profile "${currentProfileName}" is configured as readOnly.`
			: "";
		return {
			ok: false,
			error: "Write operation blocked: connection is read-only",
			code: "READ_ONLY",
			hint: `This connection is in read-only mode.${profileHint} Remove readOnly from the profile config to allow writes.`,
		};
	}

	if (error.code === "28P01") {
		return {
			ok: false,
			error: "Authentication failed",
			code: "PERMISSION_DENIED",
			hint: "Check your username and password in .pgtool.json",
		};
	}

	if (error.code === "28000") {
		const msg = error.message || "";
		const isSSL = msg.includes("no encryption") || msg.includes("SSL");
		if (isSSL) {
			return {
				ok: false,
				error: "SSL connection required by server",
				code: "CONNECTION_FAILED",
				hint: 'The server requires SSL. Add "ssl": { "rejectUnauthorized": false } to your profile in .pgtool.json (or "ssl": true if using a trusted CA)',
			};
		}
		return {
			ok: false,
			error: "Authentication failed",
			code: "PERMISSION_DENIED",
			hint: "Check your username and password in .pgtool.json",
		};
	}

	if (error.code === "3D000") {
		return {
			ok: false,
			error: "Database does not exist",
			code: "CONNECTION_FAILED",
			hint: "Verify the database name in .pgtool.json",
		};
	}

	if (
		error.code === "ECONNREFUSED" ||
		error.code === "ENOTFOUND" ||
		error.code === "ETIMEDOUT"
	) {
		return {
			ok: false,
			error: `Could not connect to database server: ${error.message}`,
			code: "CONNECTION_FAILED",
			hint: "Verify host and port in .pgtool.json and ensure PostgreSQL is running",
		};
	}

	if (error.code === "42P01") {
		return {
			ok: false,
			error: error.message,
			code: "TABLE_NOT_FOUND",
			hint: "Check that the table exists and you have permission to access it",
		};
	}

	if (error.code === "3F000") {
		return {
			ok: false,
			error: error.message,
			code: "SCHEMA_NOT_FOUND",
			hint: "Check that the schema exists",
		};
	}

	if (error.code === "42501") {
		return {
			ok: false,
			error: error.message,
			code: "PERMISSION_DENIED",
			hint: "You don't have permission to perform this operation",
		};
	}

	if (error.code === "57014") {
		return {
			ok: false,
			error: "Query timed out",
			code: "TIMEOUT",
			hint: "The query took too long to execute. Try a simpler query or add LIMIT",
		};
	}

	return {
		ok: false,
		error: error.message,
		code: "QUERY_FAILED",
		hint: "Check your SQL syntax and table/column names",
	};
}

/**
 * Test the database connection.
 */
export async function testConnection(): Promise<{ ok: true } | ErrorResponse> {
	const result = await query("SELECT 1 as test");
	if (!result.ok) {
		return result;
	}
	return { ok: true };
}
