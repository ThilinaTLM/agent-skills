// Error codes
export type ErrorCode =
	| "API_KEY_MISSING"
	| "API_ERROR"
	| "INVALID_PARAMS"
	| "OUTPUT_ERROR"
	| "PREREQ_MISSING";

// Base response types
export interface SuccessResponse {
	ok: true;
	[key: string]: unknown;
}

export interface ErrorResponse {
	ok: false;
	error: string;
	code?: ErrorCode;
	hint?: string;
}

export type Response = SuccessResponse | ErrorResponse;

// Generate result
export interface GenerateResult {
	file: string;
	mimeType: string;
	size: number;
	prompt: string;
}
