/**
 * Resolves available HTML templates under <skill-root>/templates/.
 */

import { existsSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export const TEMPLATES_DIR = resolve(__dirname, "..", "..", "..", "templates");

export function listTemplates(): string[] {
	if (!existsSync(TEMPLATES_DIR)) return [];
	return readdirSync(TEMPLATES_DIR)
		.filter((f) => f.endsWith(".html"))
		.map((f) => f.replace(/\.html$/, ""))
		.sort();
}

export function templatePath(name: string): string {
	return resolve(TEMPLATES_DIR, `${name}.html`);
}

export function templateExists(name: string): boolean {
	return existsSync(templatePath(name));
}
