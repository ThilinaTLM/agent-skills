import pg from "pg";
import type { ErrorResponse, PgToolConfig, QueryResult } from "../types";

const { Pool } = pg;

let pool: pg.Pool | null = null;

/**
 * Initialize the database connection pool.
 */
export function initConnection(config: PgToolConfig): void {
	if (pool) {
		return;
	}

	pool = new Pool({
		host: config.host,
		port: config.port || 5432,
		database: config.database,
		user: config.user,
		password: config.password,
		connectionTimeoutMillis: 10000,
		idleTimeoutMillis: 30000,
		max: 5,
	});
}

/**
 * Close the database connection pool.
 */
export async function closeConnection(): Promise<void> {
	if (pool) {
		await pool.end();
		pool = null;
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

		// Map PostgreSQL error codes to our error codes
		if (error.code === "28P01" || error.code === "28000") {
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
