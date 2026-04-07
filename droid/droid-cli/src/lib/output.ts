/**
 * Output helpers for consistent JSON formatting.
 */

import type { ErrorCode, ErrorResponse, SuccessResponse } from "../types";

/**
 * Output success JSON and exit.
 */
export function jsonOk<T extends Record<string, unknown>>(data: T): never {
	console.log(JSON.stringify({ ok: true, ...data }, null, 0));
	process.exit(0);
}

/**
 * Output error JSON and exit.
 */
export function jsonError(
	error: string,
	code?: ErrorCode,
	hint?: string,
): never {
	const response: ErrorResponse = { ok: false, error };
	if (code) response.code = code;
	if (hint) response.hint = hint;
	console.log(JSON.stringify(response, null, 0));
	process.exit(1);
}

/**
 * Output raw JSON and exit with specified code.
 */
export function outputJson(data: unknown, exitCode = 0): never {
	console.log(JSON.stringify(data, null, 0));
	process.exit(exitCode);
}
