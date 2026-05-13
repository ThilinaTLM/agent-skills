/**
 * Resolves the absolute path to the shipped richdoc.css / richdoc.js assets,
 * located at <skill-root>/assets/ relative to this CLI.
 */

import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// src/lib/assets.ts → ../../assets/
export const ASSETS_DIR = resolve(__dirname, "..", "..", "..", "assets");

export const ASSET_FILES = ["richdoc.css", "richdoc.js"] as const;
export type AssetFile = (typeof ASSET_FILES)[number];

export function assetPath(name: AssetFile): string {
	return resolve(ASSETS_DIR, name);
}

export function assetsExist(): boolean {
	return ASSET_FILES.every((f) => existsSync(assetPath(f)));
}
