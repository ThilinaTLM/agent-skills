/**
 * Shared initialization logic for commands.
 */

import type { ErrorResponse, ResolvedConnection } from "../types";
import { loadConfig } from "./config.ts";
import {
	closeConnection,
	initConnection,
	initDaemon,
	setDaemonContext,
} from "./connection.ts";
import { formatError, outputError } from "./output.ts";

interface InitResult {
	config: ResolvedConnection;
	configPath: string;
}

interface InitOptions {
	explicitRoot?: string;
	plain: boolean;
	profileName?: string;
	readOnly?: boolean;
	allowWrites?: boolean;
}

/**
 * Initialize configuration and database connection.
 * Exits with error if initialization fails.
 */
export function initPgTool(opts: InitOptions): InitResult {
	// Validate conflicting flags
	if (opts.readOnly && opts.allowWrites) {
		const error: ErrorResponse = {
			ok: false,
			error:
				"Conflicting flags: --read-only and --allow-writes cannot be used together",
			code: "CONFIG_INVALID",
			hint: "Use either --read-only or --allow-writes, not both",
		};
		if (opts.plain) {
			console.error(formatError(error));
			process.exit(1);
		}
		outputError(error);
	}

	const configResult = loadConfig(opts.explicitRoot, opts.profileName);

	if (!configResult.ok) {
		if (opts.plain) {
			console.error(formatError(configResult));
			process.exit(1);
		}
		outputError(configResult);
	}

	// Apply read-only flag overrides
	if (opts.readOnly) {
		configResult.config.readOnly = true;
	} else if (opts.allowWrites) {
		configResult.config.readOnly = false;
	}

	// Set daemon context for query routing
	const flags = {
		readOnly: opts.readOnly,
		allowWrites: opts.allowWrites,
	};
	setDaemonContext(
		configResult.configPath,
		configResult.config.profileName,
		flags,
	);

	// Protected profiles require the daemon — block direct-only access
	if (configResult.config.protected && process.env.PGTOOL_NO_DAEMON === "1") {
		const error: ErrorResponse = {
			ok: false,
			error: `Protected profile '${configResult.config.profileName}' requires the pgtool daemon`,
			code: "PROTECTED_DENIED",
			hint: "Protected profiles cannot use direct connections. Remove PGTOOL_NO_DAEMON to allow the daemon to start.",
		};
		if (opts.plain) {
			console.error(formatError(error));
			process.exit(1);
		}
		outputError(error);
	}

	// Initialize direct connection as fallback
	initConnection(configResult.config);

	return {
		config: configResult.config,
		configPath: configResult.configPath,
	};
}

/**
 * Async initialization — call after initPgTool to start daemon.
 * This is separate because citty command run() is async but
 * we want to keep initPgTool synchronous for backward compat.
 */
export async function initDaemonConnection(): Promise<void> {
	await initDaemon();
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
