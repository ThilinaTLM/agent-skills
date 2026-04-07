/**
 * Shared initialization logic for commands.
 */

import type { ErrorResponse, PgToolConfig } from "../types";
import { loadConfig } from "./config";
import { closeConnection, initConnection } from "./connection";
import { formatError, outputError } from "./output";

interface InitResult {
	config: PgToolConfig;
	configPath: string;
}

/**
 * Initialize configuration and database connection.
 * Exits with error if initialization fails.
 */
export function initPgTool(
	explicitRoot: string | undefined,
	plain: boolean,
): InitResult {
	const configResult = loadConfig(explicitRoot);

	if (!configResult.ok) {
		if (plain) {
			console.error(formatError(configResult));
			process.exit(1);
		}
		outputError(configResult);
	}

	initConnection(configResult.config);

	return {
		config: configResult.config,
		configPath: configResult.configPath,
	};
}

/**
 * Handle an error response with proper output formatting.
 */
export function handleError(error: ErrorResponse, plain: boolean): never {
	if (plain) {
		console.error(formatError(error));
		process.exit(1);
	}
	outputError(error);
}

/**
 * Cleanup function to close connections.
 */
export async function cleanup(): Promise<void> {
	await closeConnection();
}

/**
 * Register cleanup on process exit.
 */
export function registerCleanup(): void {
	process.on("beforeExit", cleanup);
	process.on("SIGINT", async () => {
		await cleanup();
		process.exit(0);
	});
	process.on("SIGTERM", async () => {
		await cleanup();
		process.exit(0);
	});
}
