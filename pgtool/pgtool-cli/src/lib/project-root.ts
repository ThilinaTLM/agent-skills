import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";

const CONFIG_FILE = ".pgtool.json";

/**
 * Walk up directories to find a project root containing .pgtool.json file.
 * @param startDir - Starting directory (defaults to process.cwd())
 * @returns Project root path or null if not found
 */
export function findProjectRoot(startDir?: string): string | null {
	let current = resolve(startDir || process.cwd());

	while (true) {
		const configPath = resolve(current, CONFIG_FILE);
		if (existsSync(configPath)) {
			return current;
		}

		const parent = dirname(current);
		// Reached filesystem root
		if (parent === current) {
			return null;
		}
		current = parent;
	}
}

/**
 * Get the config file path, using explicit root or auto-detection.
 * @param explicitRoot - Explicit project root from --root flag
 * @returns Object with configPath and projectRoot (or null if not found)
 */
export function getConfigPath(explicitRoot?: string): {
	configPath: string;
	projectRoot: string | null;
	autoDetected: boolean;
} {
	if (explicitRoot) {
		return {
			configPath: resolve(explicitRoot, CONFIG_FILE),
			projectRoot: explicitRoot,
			autoDetected: false,
		};
	}

	const projectRoot = findProjectRoot();
	if (projectRoot) {
		return {
			configPath: resolve(projectRoot, CONFIG_FILE),
			projectRoot,
			autoDetected: true,
		};
	}

	// Fallback to cwd - will likely fail but provides better error context
	return {
		configPath: resolve(process.cwd(), CONFIG_FILE),
		projectRoot: null,
		autoDetected: false,
	};
}
