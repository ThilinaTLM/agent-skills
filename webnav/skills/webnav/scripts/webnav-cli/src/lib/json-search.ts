/**
 * Search logic for JSON files produced by elements/snapshot/observe commands.
 */

import { readFileSync } from "node:fs";

// Mirrors extension's SnapshotNode shape
interface SnapshotNode {
	ref: string;
	role: string;
	name: string;
	tag: string;
	states?: Record<string, unknown>;
	children?: SnapshotNode[];
}

// Flat item produced from either element or snapshot data
interface FlatItem {
	ref?: string;
	role?: string;
	name?: string;
	tag?: string;
	text?: string;
	states?: Record<string, unknown>;
	[key: string]: unknown;
}

export interface SearchOptions {
	pattern?: string;
	tag?: string;
	role?: string;
	ref?: string;
	limit: number;
	offset: number;
}

export interface SearchResult {
	action: "json-search";
	matches: FlatItem[];
	total: number;
	limit: number;
	offset: number;
	fileType:
		| "elements"
		| "snapshot-tree"
		| "snapshot-compact"
		| "console"
		| "errors"
		| "network";
}

type FileType = SearchResult["fileType"];

function detectFileType(data: unknown): { type: FileType; data: unknown } {
	if (typeof data === "string") {
		return { type: "snapshot-compact", data };
	}
	if (Array.isArray(data)) {
		if (data.length === 0) return { type: "elements", data };
		const first = data[0];
		if (first && typeof first === "object") {
			if ("children" in first) {
				return { type: "snapshot-tree", data };
			}
			if ("ref" in first && "role" in first && !("type" in first)) {
				return { type: "snapshot-tree", data };
			}
			if ("level" in first && "text" in first && "timestamp" in first) {
				return { type: "console", data };
			}
			if ("message" in first && "line" in first && "col" in first) {
				return { type: "errors", data };
			}
			if ("url" in first && "method" in first && "status" in first) {
				return { type: "network", data };
			}
			if ("tag" in first && "type" in first) {
				return { type: "elements", data };
			}
		}
		throw new Error(
			"Unsupported file format. json-search only supports files created by webnav snapshot, elements, console, errors, network, or observe commands.",
		);
	}
	throw new Error(
		"Unsupported file format. json-search only supports files created by webnav snapshot, elements, console, errors, network, or observe commands.",
	);
}

function flattenSnapshotTree(nodes: SnapshotNode[]): FlatItem[] {
	const result: FlatItem[] = [];
	function walk(list: SnapshotNode[]) {
		for (const node of list) {
			result.push({
				ref: node.ref,
				role: node.role,
				name: node.name,
				tag: node.tag,
				states: node.states,
			});
			if (node.children) walk(node.children);
		}
	}
	walk(nodes);
	return result;
}

// Parse compact format lines like: @e1 role "name" [key=val key2=val2]
function parseCompactSnapshot(text: string): FlatItem[] {
	const items: FlatItem[] = [];
	for (const raw of text.split("\n")) {
		const line = raw.trim();
		if (!line) continue;

		// Match: @ref role "name" [states] or @ref role [states] or @ref role "name" or @ref role
		const match = line.match(
			/^(@\w+)\s+(\S+)(?:\s+"([^"]*)")?(?:\s+\[([^\]]*)\])?/,
		);
		if (!match) continue;

		const item: FlatItem = {
			ref: match[1],
			role: match[2],
		};
		if (match[3] !== undefined) item.name = match[3];
		if (match[4]) {
			const states: Record<string, unknown> = {};
			for (const pair of match[4].split(/\s+/)) {
				const eq = pair.indexOf("=");
				if (eq > 0) {
					states[pair.slice(0, eq)] = pair.slice(eq + 1);
				}
			}
			item.states = states;
		}
		items.push(item);
	}
	return items;
}

function matchesFilters(item: FlatItem, options: SearchOptions): boolean {
	if (options.ref) {
		if (item.ref !== options.ref) return false;
	}
	if (options.tag) {
		if (!item.tag || item.tag.toLowerCase() !== options.tag.toLowerCase())
			return false;
	}
	if (options.role) {
		if (!item.role || item.role.toLowerCase() !== options.role.toLowerCase())
			return false;
	}
	if (options.pattern) {
		const p = options.pattern.toLowerCase();
		const searchable = [
			item.ref,
			item.role,
			item.name,
			item.tag,
			item.text,
			// Include other string fields from element data
			...(typeof item.ariaLabel === "string" ? [item.ariaLabel] : []),
			...(typeof item.placeholder === "string" ? [item.placeholder] : []),
			...(typeof item.label === "string" ? [item.label] : []),
			...(typeof item.id === "string" ? [item.id] : []),
			...(typeof item.href === "string" ? [item.href] : []),
			...(typeof item.value === "string" ? [item.value] : []),
			// Console fields
			...(typeof item.level === "string" ? [item.level] : []),
			// Error fields
			...(typeof item.message === "string" ? [item.message] : []),
			...(typeof item.source === "string" ? [item.source] : []),
			// Network fields
			...(typeof item.url === "string" ? [item.url] : []),
			...(typeof item.method === "string" ? [item.method] : []),
			...(typeof item.statusText === "string" ? [item.statusText] : []),
			...(typeof item.type === "string" ? [item.type] : []),
			...(typeof item.requestBody === "string" ? [item.requestBody] : []),
			...(typeof item.responseBody === "string" ? [item.responseBody] : []),
		];
		const found = searchable.some(
			(v) => typeof v === "string" && v.toLowerCase().includes(p),
		);
		if (!found) return false;
	}
	return true;
}

export function searchJsonFile(
	filepath: string,
	options: SearchOptions,
): SearchResult {
	const raw = readFileSync(filepath, "utf-8");
	const parsed: unknown = JSON.parse(raw);

	const { type, data } = detectFileType(parsed);

	let items: FlatItem[];
	switch (type) {
		case "elements":
		case "console":
		case "errors":
		case "network":
			items = (data as FlatItem[]) || [];
			break;
		case "snapshot-tree":
			items = flattenSnapshotTree(data as SnapshotNode[]);
			break;
		case "snapshot-compact":
			items = parseCompactSnapshot(data as string);
			break;
	}

	const filtered = items.filter((item) => matchesFilters(item, options));
	const total = filtered.length;
	const sliced = filtered.slice(options.offset, options.offset + options.limit);

	return {
		action: "json-search",
		matches: sliced,
		total,
		limit: options.limit,
		offset: options.offset,
		fileType: type,
	};
}
