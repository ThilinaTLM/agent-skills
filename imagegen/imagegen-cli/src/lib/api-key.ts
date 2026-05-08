/**
 * Resolve the Gemini API key.
 *
 * Order:
 *   1. `GEMINI_API_KEY` environment variable (wins; supports CI / explicit override).
 *   2. `.gemini-key` file walked up from `cwd` to filesystem root (project-local).
 *   3. `~/.gemini-key` in the user's home directory (machine-wide default).
 *
 * The file must contain just the raw key (whitespace is trimmed). Users should
 * add `.gemini-key` to `.gitignore` since it holds a secret.
 */

import { readFile, stat } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";

export type ApiKeySource = "env" | "file";

export interface ResolvedApiKey {
	key: string;
	source: ApiKeySource;
	/** Absolute path to the file when source === "file". */
	path?: string;
}

const KEY_FILENAME = ".gemini-key";

async function fileExists(p: string): Promise<boolean> {
	try {
		const s = await stat(p);
		return s.isFile();
	} catch {
		return false;
	}
}

async function findProjectKeyFile(startDir: string): Promise<string | null> {
	let dir = resolve(startDir);
	// Cap iterations defensively; we stop when dirname returns the same path (filesystem root).
	for (let i = 0; i < 64; i++) {
		const candidate = resolve(dir, KEY_FILENAME);
		if (await fileExists(candidate)) return candidate;
		const parent = dirname(dir);
		if (parent === dir) return null;
		dir = parent;
	}
	return null;
}

async function readKeyFile(path: string): Promise<string | null> {
	const raw = await readFile(path, "utf8");
	const key = raw.trim();
	return key || null;
}

export async function resolveApiKey(
	cwd: string = process.cwd(),
): Promise<ResolvedApiKey | null> {
	const fromEnv = process.env.GEMINI_API_KEY?.trim();
	if (fromEnv) {
		return { key: fromEnv, source: "env" };
	}

	const projectPath = await findProjectKeyFile(cwd);
	if (projectPath) {
		const key = await readKeyFile(projectPath);
		if (key) return { key, source: "file", path: projectPath };
	}

	const home = homedir();
	if (home) {
		const homePath = resolve(home, KEY_FILENAME);
		if (await fileExists(homePath)) {
			const key = await readKeyFile(homePath);
			if (key) return { key, source: "file", path: homePath };
		}
	}

	return null;
}
