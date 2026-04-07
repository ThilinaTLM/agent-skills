/**
 * UI hierarchy dump functions using uiautomator.
 */

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { XMLParser } from "fast-xml-parser";
import type { ADB } from "./adb";
import { UIElement } from "./ui-element";

const REMOTE_PATH = "/sdcard/ui_dump.xml";
const MAX_RETRIES = 3;

/**
 * Dump and parse UI hierarchy with retry logic for Android 14+.
 */
export async function dumpUIHierarchy(adb: ADB): Promise<UIElement[]> {
	// Try uiautomator dump with retries (helps with "could not get idle state" on newer Android)
	for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
		const result = await adb.shellUnchecked("uiautomator", "dump", REMOTE_PATH);
		const output = result.stdout + result.stderr;

		if (!output.includes("ERROR")) {
			break;
		}

		// Wait before retry - UI might not be idle
		if (attempt < MAX_RETRIES - 1) {
			await Bun.sleep(500);
		}

		// All retries failed
		if (attempt === MAX_RETRIES - 1) {
			return [];
		}
	}

	// Pull to temp file
	const localPath = path.join(os.tmpdir(), `ui_dump_${Date.now()}.xml`);

	try {
		await adb.pull(REMOTE_PATH, localPath);
		await adb.shellUnchecked("rm", REMOTE_PATH);

		if (!fs.existsSync(localPath) || fs.statSync(localPath).size === 0) {
			return [];
		}

		// Parse XML
		const xmlContent = fs.readFileSync(localPath, "utf-8");
		const parser = new XMLParser({
			ignoreAttributes: false,
			attributeNamePrefix: "@_",
		});

		const parsed = parser.parse(xmlContent);

		// Extract all nodes recursively
		const elements: UIElement[] = [];
		extractNodes(parsed, elements);

		return elements;
	} catch {
		return [];
	} finally {
		// Clean up temp file
		if (fs.existsSync(localPath)) {
			fs.unlinkSync(localPath);
		}
	}
}

/**
 * Recursively extract nodes from parsed XML.
 */
function extractNodes(
	obj: unknown,
	elements: UIElement[],
	visited = new Set<unknown>(),
): void {
	if (!obj || typeof obj !== "object" || visited.has(obj)) {
		return;
	}
	visited.add(obj);

	const record = obj as Record<string, unknown>;

	// Check if this is a node element
	if (record["@_bounds"]) {
		const elem = new UIElement(record as Record<string, string>);
		if (!elem.isEmpty()) {
			elements.push(elem);
		}
	}

	// Recurse into child nodes
	if (record.node) {
		const nodes = Array.isArray(record.node) ? record.node : [record.node];
		for (const node of nodes) {
			extractNodes(node, elements, visited);
		}
	}

	// Check other properties that might contain nodes
	for (const key of Object.keys(record)) {
		if (key !== "node" && typeof record[key] === "object") {
			extractNodes(record[key], elements, visited);
		}
	}
}
