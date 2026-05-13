// Error codes
export type ErrorCode =
	| "INVALID_PARAMS"
	| "FILE_EXISTS"
	| "TEMPLATE_NOT_FOUND"
	| "INPUT_ERROR"
	| "OUTPUT_ERROR"
	| "LINT_ERRORS"
	| "PREREQ_MISSING";

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

export type LintSeverity = "error" | "warn";

export interface LintIssue {
	severity: LintSeverity;
	rule: string;
	tag?: string;
	attr?: string;
	line?: number;
	message: string;
}
