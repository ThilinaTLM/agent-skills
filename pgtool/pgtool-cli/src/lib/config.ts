import { existsSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import type {
	ErrorResponse,
	PgToolFileConfig,
	PgToolProfileConfig,
	ResolvedConnection,
} from "../types";
import { getConfigPath } from "./project-root.ts";

interface ConfigResult {
	ok: true;
	config: ResolvedConnection;
	configPath: string;
}

interface FileConfigResult {
	ok: true;
	fileConfig: PgToolFileConfig;
	configPath: string;
}

/**
 * Load and validate the .pgtool.json configuration file, resolve the specified profile.
 * @param explicitRoot - Explicit project root from --root flag
 * @param profileName - Profile to resolve (from --profile flag or PGTOOL_PROFILE env)
 * @returns Resolved connection config or error response
 */
export function loadConfig(
	explicitRoot?: string,
	profileName?: string,
): ConfigResult | ErrorResponse {
	const fileResult = loadFileConfig(explicitRoot);
	if (!fileResult.ok) return fileResult;

	const resolved = resolveProfile(
		fileResult.fileConfig,
		profileName,
		fileResult.configPath,
	);
	if (!resolved.ok) return resolved;

	return {
		ok: true,
		config: resolved.config,
		configPath: fileResult.configPath,
	};
}

/**
 * Load and parse the config file without resolving a specific profile.
 * Used by the `profiles` command to list all profiles.
 */
export function loadFileConfig(
	explicitRoot?: string,
): FileConfigResult | ErrorResponse {
	// Support passing a direct config file path (used by daemon)
	const configPath = explicitRoot?.endsWith(".pgtool.json")
		? explicitRoot
		: getConfigPath(explicitRoot).configPath;

	if (!existsSync(configPath)) {
		return {
			ok: false,
			error: "Configuration file not found",
			code: "CONFIG_NOT_FOUND",
			hint: `Create a .pgtool.json file in your project root. Example:\n{\n  "profiles": {\n    "dev": {\n      "host": "localhost",\n      "port": 5432,\n      "database": "mydb",\n      "user": "postgres",\n      "passwordEnv": "PGPASSWORD"\n    }\n  },\n  "default": "dev"\n}`,
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

	if (typeof rawConfig !== "object" || rawConfig === null) {
		return {
			ok: false,
			error: "Configuration must be a JSON object",
			code: "CONFIG_INVALID",
			hint: "Check your .pgtool.json file format",
		};
	}

	const fileConfig = normalizeConfig(rawConfig as Record<string, unknown>);
	if (!fileConfig.ok) return fileConfig;

	return {
		ok: true,
		fileConfig: fileConfig.config,
		configPath,
	};
}

// ---------------------------------------------------------------------------
// Format detection & normalization
// ---------------------------------------------------------------------------

function detectFormat(raw: Record<string, unknown>): "legacy" | "multi" {
	if ("profiles" in raw && typeof raw.profiles === "object") return "multi";
	if ("host" in raw || "url" in raw) return "legacy";
	return "multi"; // empty object defaults to multi (will fail validation)
}

function normalizeConfig(
	raw: Record<string, unknown>,
): { ok: true; config: PgToolFileConfig } | ErrorResponse {
	const format = detectFormat(raw);

	if (format === "legacy") {
		return {
			ok: true,
			config: {
				profiles: { default: raw as unknown as PgToolProfileConfig },
				default: "default",
			},
		};
	}

	// Multi-profile format
	if (
		typeof raw.profiles !== "object" ||
		raw.profiles === null ||
		Array.isArray(raw.profiles)
	) {
		return {
			ok: false,
			error: '"profiles" must be an object mapping profile names to configs',
			code: "CONFIG_INVALID",
			hint: 'Add a "profiles" object to your .pgtool.json',
		};
	}

	const profiles = raw.profiles as Record<string, unknown>;
	if (Object.keys(profiles).length === 0) {
		return {
			ok: false,
			error: "No profiles defined",
			code: "CONFIG_INVALID",
			hint: "Add at least one profile to the profiles object",
		};
	}

	if (raw.default !== undefined && typeof raw.default !== "string") {
		return {
			ok: false,
			error: '"default" must be a string (profile name)',
			code: "CONFIG_INVALID",
			hint: 'Set "default" to the name of a profile defined in "profiles"',
		};
	}

	return {
		ok: true,
		config: {
			profiles: profiles as Record<string, PgToolProfileConfig>,
			default: raw.default as string | undefined,
		},
	};
}

// ---------------------------------------------------------------------------
// Profile resolution
// ---------------------------------------------------------------------------

/**
 * Resolve a specific profile from the file config into a ResolvedConnection.
 * Priority: explicit profileName > PGTOOL_PROFILE env > config default > first profile
 */
function resolveProfile(
	fileConfig: PgToolFileConfig,
	profileName: string | undefined,
	configPath: string,
): { ok: true; config: ResolvedConnection } | ErrorResponse {
	const effectiveProfile =
		profileName ||
		process.env.PGTOOL_PROFILE ||
		fileConfig.default ||
		Object.keys(fileConfig.profiles)[0];

	if (!effectiveProfile) {
		return {
			ok: false,
			error: "No profile specified and no default configured",
			code: "CONFIG_INVALID",
			hint: 'Use --profile <name>, set PGTOOL_PROFILE env var, or add "default" to your config',
		};
	}

	const profile = fileConfig.profiles[effectiveProfile];
	if (!profile) {
		const available = Object.keys(fileConfig.profiles).join(", ");
		return {
			ok: false,
			error: `Profile "${effectiveProfile}" not found`,
			code: "CONFIG_INVALID",
			hint: `Available profiles: ${available}`,
		};
	}

	// Validate the profile
	const validationError = validateProfile(profile, effectiveProfile);
	if (validationError) return validationError;

	// Resolve to concrete connection values
	return resolveConnection(profile, effectiveProfile);
}

// ---------------------------------------------------------------------------
// Profile validation
// ---------------------------------------------------------------------------

function validateProfile(
	profile: PgToolProfileConfig,
	name: string,
): ErrorResponse | null {
	// Mutual exclusion: url vs field-based
	const exclusionError = validateMutualExclusion(profile, name);
	if (exclusionError) return exclusionError;

	if (profile.url) {
		return validateUrlProfile(profile, name);
	}
	return validateFieldProfile(profile, name);
}

function validateMutualExclusion(
	profile: PgToolProfileConfig,
	name: string,
): ErrorResponse | null {
	if (!profile.url) return null;

	const fieldBased = [
		"host",
		"database",
		"user",
		"password",
		"passwordEnv",
	] as const;
	const present = fieldBased.filter(
		(f) => profile[f] !== undefined && profile[f] !== "",
	);

	if (present.length > 0) {
		return {
			ok: false,
			error: `Profile "${name}": "url" cannot be combined with ${present.map((f) => `"${f}"`).join(", ")}`,
			code: "CONFIG_INVALID",
			hint: "Use either a connection URL or individual host/database/user/password fields, not both",
		};
	}

	return null;
}

function validateUrlProfile(
	profile: PgToolProfileConfig,
	name: string,
): ErrorResponse | null {
	const url = profile.url as string;
	if (!url.startsWith("postgres://") && !url.startsWith("postgresql://")) {
		return {
			ok: false,
			error: `Profile "${name}": invalid connection URL`,
			code: "CONFIG_INVALID",
			hint: 'URL must start with "postgres://" or "postgresql://"',
		};
	}

	try {
		new URL(url);
	} catch {
		return {
			ok: false,
			error: `Profile "${name}": malformed connection URL`,
			code: "CONFIG_INVALID",
			hint: "Check the URL format: postgres://user:password@host:port/database",
		};
	}

	return validateCommonFields(profile, name);
}

function validateFieldProfile(
	profile: PgToolProfileConfig,
	name: string,
): ErrorResponse | null {
	const requiredFields = ["host", "database", "user"] as const;
	for (const field of requiredFields) {
		if (typeof profile[field] !== "string" || profile[field] === "") {
			return {
				ok: false,
				error: `Profile "${name}": missing or invalid required field "${field}"`,
				code: "CONFIG_INVALID",
				hint: `Add "${field}" to the "${name}" profile`,
			};
		}
	}

	if (profile.port !== undefined) {
		if (
			typeof profile.port !== "number" ||
			profile.port < 1 ||
			profile.port > 65535
		) {
			return {
				ok: false,
				error: `Profile "${name}": invalid port number`,
				code: "CONFIG_INVALID",
				hint: "Port must be a number between 1 and 65535",
			};
		}
	}

	if (!profile.password && !profile.passwordEnv) {
		return {
			ok: false,
			error: `Profile "${name}": no password configuration provided`,
			code: "CONFIG_INVALID",
			hint: `Add either "password" or "passwordEnv" to the "${name}" profile`,
		};
	}

	return validateCommonFields(profile, name);
}

function validateCommonFields(
	profile: PgToolProfileConfig,
	name: string,
): ErrorResponse | null {
	if (
		profile.ssl !== undefined &&
		profile.ssl !== true &&
		profile.ssl !== false
	) {
		if (typeof profile.ssl !== "object" || profile.ssl === null) {
			return {
				ok: false,
				error: `Profile "${name}": invalid ssl configuration`,
				code: "CONFIG_INVALID",
				hint: "ssl must be true, false, or an object with optional keys: rejectUnauthorized, ca, cert, key",
			};
		}
	}

	return null;
}

// ---------------------------------------------------------------------------
// Connection resolution
// ---------------------------------------------------------------------------

function resolveConnection(
	profile: PgToolProfileConfig,
	profileName: string,
): { ok: true; config: ResolvedConnection } | ErrorResponse {
	if (profile.url) {
		return resolveUrlConnection(profile, profileName);
	}
	return resolveFieldConnection(profile, profileName);
}

function resolveUrlConnection(
	profile: PgToolProfileConfig,
	profileName: string,
): { ok: true; config: ResolvedConnection } | ErrorResponse {
	const parsed = new URL(profile.url as string);

	return {
		ok: true,
		config: {
			host: parsed.hostname,
			port: parsed.port ? Number.parseInt(parsed.port, 10) : 5432,
			database: parsed.pathname.replace(/^\//, ""),
			user: decodeURIComponent(parsed.username),
			password: decodeURIComponent(parsed.password),
			schema: profile.schema || "public",
			ssl: profile.ssl,
			readOnly: profile.readOnly ?? false,
			protected: profile.protected ?? false,
			profileName,
			url: profile.url,
		},
	};
}

function resolveFieldConnection(
	profile: PgToolProfileConfig,
	profileName: string,
): { ok: true; config: ResolvedConnection } | ErrorResponse {
	let password = profile.password;

	if (profile.passwordEnv && !password) {
		const envPassword = process.env[profile.passwordEnv];
		if (!envPassword) {
			return {
				ok: false,
				error: `Environment variable ${profile.passwordEnv} is not set`,
				code: "CONFIG_INVALID",
				hint: `Set the ${profile.passwordEnv} environment variable with your database password`,
			};
		}
		password = envPassword;
	}

	return {
		ok: true,
		config: {
			host: profile.host as string,
			port: profile.port || 5432,
			database: profile.database as string,
			user: profile.user as string,
			password: password as string,
			schema: profile.schema || "public",
			ssl: profile.ssl,
			readOnly: profile.readOnly ?? false,
			protected: profile.protected ?? false,
			profileName,
		},
	};
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/**
 * Get the default schema from config or fallback to 'public'.
 */
export function getDefaultSchema(config: ResolvedConnection): string {
	return config.schema || "public";
}
