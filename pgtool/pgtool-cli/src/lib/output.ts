/**
 * Output helpers for consistent formatting between JSON and plain text modes.
 */

import type { ErrorResponse } from "../types";

/**
 * Output JSON response and exit with appropriate code.
 */
export function outputJson(data: unknown, exitCode = 0): never {
	console.log(JSON.stringify(data, null, 2));
	process.exit(exitCode);
}

/**
 * Output error response in JSON format and exit.
 */
export function outputError(error: ErrorResponse): never {
	outputJson(error, 1);
}

/**
 * Format error for plain text output.
 */
export function formatError(error: ErrorResponse): string {
	let output = `Error: ${error.error}`;
	if (error.hint) {
		output += `\nHint: ${error.hint}`;
	}
	return output;
}

/**
 * Format bytes to human-readable size.
 */
export function formatBytes(bytes: number | null): string | null {
	if (bytes === null) {
		return null;
	}

	const units = ["B", "KB", "MB", "GB", "TB"];
	let unitIndex = 0;
	let size = bytes;

	while (size >= 1024 && unitIndex < units.length - 1) {
		size /= 1024;
		unitIndex++;
	}

	return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

/**
 * Create a simple table for plain text output.
 */
export function formatTable(
	headers: string[],
	rows: string[][],
	options: { padding?: number } = {},
): string {
	const padding = options.padding ?? 2;

	// Calculate column widths
	const widths = headers.map((h, i) => {
		const maxRowWidth = rows.reduce(
			(max, row) => Math.max(max, (row[i] ?? "").length),
			0,
		);
		return Math.max(h.length, maxRowWidth);
	});

	// Format header
	const headerLine = headers
		.map((h, i) => h.padEnd(widths[i] + padding))
		.join("");
	const separator = widths.map((w) => "─".repeat(w + padding)).join("");

	// Format rows
	const rowLines = rows.map((row) =>
		row.map((cell, i) => (cell ?? "").padEnd(widths[i] + padding)).join(""),
	);

	return [headerLine, separator, ...rowLines].join("\n");
}
