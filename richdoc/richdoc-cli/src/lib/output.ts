/**
 * Output helpers for consistent JSON formatting.
 */

import type { ErrorCode, ErrorResponse } from "../types/index.ts";

export function jsonOk<T extends Record<string, unknown>>(data: T): never {
	console.log(JSON.stringify({ ok: true, ...data }, null, 0));
	process.exit(0);
}

export function jsonError(
	error: string,
	code?: ErrorCode,
	hint?: string,
	extra?: Record<string, unknown>,
): never {
	const response: ErrorResponse & Record<string, unknown> = {
		ok: false,
		error,
	};
	if (code) response.code = code;
	if (hint) response.hint = hint;
	if (extra) Object.assign(response, extra);
	console.log(JSON.stringify(response, null, 0));
	process.exit(1);
}
