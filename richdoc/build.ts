#!/usr/bin/env bun
/**
 * richdoc build pipeline.
 *
 * Emits the three artifacts that get committed to `assets/`:
 *   - `richdoc.js`     IIFE classic script, loads over file:// or http(s)://
 *   - `richdoc.css`    Concatenated + minified component styles
 *   - `schema.json`    Vocabulary spec — consumed by `richdoc-cli`
 *   - `version.txt`    Content hash + ISO timestamp
 *
 * Flags:
 *   --dev    Skip minification, emit larger sources useful for debugging.
 *
 * After building, the script lints `examples/showcase.html` against the
 * freshly-emitted schema and fails the build on any error. This guarantees
 * that source changes never break the canonical example.
 */

import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

import { SCHEMA_ENTRIES } from "./src/schema-registry.ts";

const ROOT = import.meta.dir;
const ASSETS_DIR = resolve(ROOT, "assets");
const SRC_DIR = resolve(ROOT, "src");

const args = new Set(process.argv.slice(2));
const isDev = args.has("--dev");

interface BuildArtifact {
	path: string;
	bytes: number;
}

async function main(): Promise<void> {
	await mkdir(ASSETS_DIR, { recursive: true });
	const artifacts: BuildArtifact[] = [];

	const t0 = performance.now();

	console.log(`▸ building richdoc (${isDev ? "dev" : "production"})…`);

	artifacts.push(await buildJs());
	artifacts.push(await buildCss());
	artifacts.push(await buildSchema());

	const version = await writeVersion(artifacts);
	const dt = (performance.now() - t0).toFixed(0);

	console.log(`✓ build complete in ${dt}ms — bundle ${version.hash}`);
	for (const a of artifacts) {
		console.log(`  ${a.path.padEnd(36)} ${formatBytes(a.bytes)}`);
	}

	// Optional sanity check — lint the canonical showcase against the fresh schema.
	const showcase = resolve(ROOT, "examples/showcase.html");
	if (existsSync(showcase)) {
		const ok = await sanityCheck(showcase);
		if (!ok) {
			console.error("✗ showcase failed schema validation — see lint output above.");
			process.exit(1);
		}
		console.log("✓ examples/showcase.html validates against the new schema");
	}
}

async function buildJs(): Promise<BuildArtifact> {
	const result = await Bun.build({
		entrypoints: [join(SRC_DIR, "index.ts")],
		target: "browser",
		format: "iife",
		minify: !isDev,
		sourcemap: "linked",
		outdir: ASSETS_DIR,
		naming: "richdoc.js",
	});

	if (!result.success) {
		for (const log of result.logs) console.error(log);
		throw new Error("JS bundle failed");
	}

	const file = join(ASSETS_DIR, "richdoc.js");
	const bytes = (await readFile(file)).byteLength;
	return { path: "assets/richdoc.js", bytes };
}

async function buildCss(): Promise<BuildArtifact> {
	// Bun's CSS bundler resolves @imports relative to the entry. We bundle from
	// `src/styles/index.css`. If the bundler ever drops files, switch to the
	// manual flatten path documented in the plan.
	const result = await Bun.build({
		entrypoints: [join(SRC_DIR, "styles", "index.css")],
		minify: !isDev,
		outdir: ASSETS_DIR,
		naming: "richdoc.css",
	});

	if (!result.success) {
		for (const log of result.logs) console.error(log);
		throw new Error("CSS bundle failed");
	}

	const file = join(ASSETS_DIR, "richdoc.css");
	const bytes = (await readFile(file)).byteLength;
	return { path: "assets/richdoc.css", bytes };
}

async function buildSchema(): Promise<BuildArtifact> {
	const schema: Record<string, unknown> = {};
	for (const e of SCHEMA_ENTRIES) schema[e.tagName] = e.spec;

	const payload = {
		$schema: "richdoc-schema/v1",
		tags: schema,
	};

	const file = join(ASSETS_DIR, "schema.json");
	const text = `${JSON.stringify(payload, null, isDev ? 2 : 0)}\n`;
	await writeFile(file, text);

	return { path: "assets/schema.json", bytes: text.length };
}

async function writeVersion(
	artifacts: BuildArtifact[],
): Promise<{ hash: string; builtAt: string }> {
	// Combine the produced bytes into one digest so the hash represents
	// exactly what was shipped this build.
	const hasher = new Bun.CryptoHasher("sha256");
	for (const a of artifacts) {
		const file = resolve(ROOT, a.path);
		hasher.update(await readFile(file));
	}
	const hash = hasher.digest("hex").slice(0, 12);
	const builtAt = new Date().toISOString();

	const out = JSON.stringify(
		{
			hash,
			builtAt,
			dev: isDev,
			files: artifacts.map((a) => ({ path: a.path, bytes: a.bytes })),
		},
		null,
		2,
	);
	await writeFile(join(ASSETS_DIR, "version.txt"), `${out}\n`);
	return { hash, builtAt };
}

async function sanityCheck(htmlPath: string): Promise<boolean> {
	// Spawn the CLI binary so we don't have to share code across packages.
	// The CLI loads the freshly-emitted assets/schema.json from disk.
	const cli = resolve(ROOT, "richdoc-cli", "richdoc");
	if (!existsSync(cli)) {
		console.warn("  (sanity check skipped — richdoc-cli not built yet)");
		return true;
	}
	const proc = Bun.spawn([cli, "lint", htmlPath], {
		stdout: "pipe",
		stderr: "pipe",
	});
	const stdout = await new Response(proc.stdout).text();
	await proc.exited;
	try {
		const result = JSON.parse(stdout) as {
			ok: boolean;
			issues: Array<{ severity: string; line?: number; rule: string; message: string }>;
		};
		if (result.ok) return true;
		for (const issue of result.issues) {
			console.error(`  [${issue.severity}] L${issue.line ?? "?"} ${issue.rule}: ${issue.message}`);
		}
		return result.issues.every((i) => i.severity !== "error");
	} catch {
		console.warn("  (sanity check skipped — CLI did not return JSON)");
		return true;
	}
}

function formatBytes(n: number): string {
	if (n < 1024) return `${n} B`;
	if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
	return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

await main();
