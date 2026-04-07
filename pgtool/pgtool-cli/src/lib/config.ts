import { existsSync, readFileSync } from "node:fs";
import type { ErrorResponse, PgToolConfig } from "../types";
import { getConfigPath } from "./project-root";

interface ConfigResult {
	ok: true;
	config: PgToolConfig;
	configPath: string;
}

/**
 * Load and validate the .pgtool.json configuration file.
 * @param explicitRoot - Explicit project root from --root flag
 * @returns Config object or error response
 */
export function loadConfig(
	explicitRoot?: string,
): ConfigResult | ErrorResponse {
	const { configPath, projectRoot } = getConfigPath(explicitRoot);

	if (!existsSync(configPath)) {
		return {
			ok: false,
			error: "Configuration file not found",
			code: "CONFIG_NOT_FOUND",
			hint: `Create a .pgtool.json file in your project root with database connection details. Example:\n{\n  "host": "localhost",\n  "port": 5432,\n  "database": "mydb",\n  "user": "postgres",\n  "passwordEnv": "PGPASSWORD"\n}`,
		};
	}

	let rawConfig: unknown;
	try {
		const content = readFileSync(configPath, "utf-8");
		rawConfig = JSON.parse(content);
	} catch (e) {
		return {
			ok: false,
			error: `Failed to parse configuration file: ${e instanceof Error ? e.message : String(e)}`,
			code: "CONFIG_INVALID",
			hint: "Ensure .pgtool.json contains valid JSON",
		};
	}

	const validationError = validateConfig(rawConfig);
	if (validationError) {
		return validationError;
	}

	const config = rawConfig as PgToolConfig;

	// Resolve password from environment variable if specified
	if (config.passwordEnv && !config.password) {
		const envPassword = process.env[config.passwordEnv];
		if (!envPassword) {
			return {
				ok: false,
				error: `Environment variable ${config.passwordEnv} is not set`,
				code: "CONFIG_INVALID",
				hint: `Set the ${config.passwordEnv} environment variable with your database password`,
			};
		}
		config.password = envPassword;
	}

	return {
		ok: true,
		config,
		configPath,
	};
}

/**
 * Validate the configuration object structure.
 */
function validateConfig(config: unknown): ErrorResponse | null {
	if (typeof config !== "object" || config === null) {
		return {
			ok: false,
			error: "Configuration must be a JSON object",
			code: "CONFIG_INVALID",
			hint: "Check your .pgtool.json file format",
		};
	}

	const cfg = config as Record<string, unknown>;

	// Required fields
	const requiredFields = ["host", "database", "user"] as const;
	for (const field of requiredFields) {
		if (typeof cfg[field] !== "string" || cfg[field] === "") {
			return {
				ok: false,
				error: `Missing or invalid required field: ${field}`,
				code: "CONFIG_INVALID",
				hint: `Add "${field}" to your .pgtool.json configuration`,
			};
		}
	}

	// Port validation
	if (cfg.port !== undefined) {
		if (typeof cfg.port !== "number" || cfg.port < 1 || cfg.port > 65535) {
			return {
				ok: false,
				error: "Invalid port number",
				code: "CONFIG_INVALID",
				hint: "Port must be a number between 1 and 65535",
			};
		}
	}

	// Password or passwordEnv must be provided
	if (!cfg.password && !cfg.passwordEnv) {
		return {
			ok: false,
			error: "No password configuration provided",
			code: "CONFIG_INVALID",
			hint: 'Add either "password" or "passwordEnv" to your .pgtool.json',
		};
	}

	return null;
}

/**
 * Get the default schema from config or fallback to 'public'.
 */
export function getDefaultSchema(config: PgToolConfig): string {
	return config.schema || "public";
}
