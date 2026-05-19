/**
 * Data parsing for rd-chart. Accepts JSON arrays, CSV, or a compact
 * "value list" format (numbers + sibling labels attribute).
 */

import { stripCommonIndent } from "../../lib/text.ts";

export type Row = Record<string, string | number>;

export function parseData(raw: string, format: "json" | "csv" | "auto"): Row[] {
	const text = stripCommonIndent(raw).trim();
	if (!text) return [];

	if (format === "json" || (format === "auto" && /^[\[{]/.test(text))) {
		try {
			const v = JSON.parse(text);
			if (Array.isArray(v)) return v.map(coerce);
			return [];
		} catch {
			return [];
		}
	}
	if (format === "csv" || format === "auto") {
		return parseCsv(text);
	}
	return [];
}

/**
 * Build rows from a compact "values" + "labels" attribute pair.
 *   values="3,5,2,8"  labels="Jan,Feb,Mar,Apr"
 *      → [{label:"Jan",value:3}, ...]
 */
export function parseValues(values: string, labels: string | null): Row[] {
	const vs = values
		.split(",")
		.map((s) => s.trim())
		.filter(Boolean)
		.map(Number);
	const ls = labels
		? labels
				.split(",")
				.map((s) => s.trim())
				.filter(Boolean)
		: vs.map((_, i) => String(i + 1));
	const rows: Row[] = [];
	for (let i = 0; i < vs.length; i++) {
		rows.push({ label: ls[i] ?? String(i + 1), value: vs[i] });
	}
	return rows;
}

function parseCsv(text: string): Row[] {
	const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
	if (!lines.length) return [];
	const headers = splitCsvLine(lines[0]);
	const rows: Row[] = [];
	for (let i = 1; i < lines.length; i++) {
		const cells = splitCsvLine(lines[i]);
		const row: Row = {};
		for (let j = 0; j < headers.length; j++) {
			const key = headers[j] ?? `col${j}`;
			const cell = cells[j] ?? "";
			row[key] = coerceCell(cell);
		}
		rows.push(row);
	}
	return rows;
}

function splitCsvLine(line: string): string[] {
	const out: string[] = [];
	let cur = "";
	let q = false;
	for (let i = 0; i < line.length; i++) {
		const ch = line[i];
		if (q) {
			if (ch === '"' && line[i + 1] === '"') {
				cur += '"';
				i++;
			} else if (ch === '"') {
				q = false;
			} else {
				cur += ch;
			}
		} else if (ch === '"') {
			q = true;
		} else if (ch === ",") {
			out.push(cur);
			cur = "";
		} else {
			cur += ch;
		}
	}
	out.push(cur);
	return out.map((s) => s.trim());
}

function coerceCell(s: string): string | number {
	if (s === "") return s;
	const n = Number(s);
	if (Number.isFinite(n) && /^-?[\d.,eE+\-]+$/.test(s)) return n;
	return s;
}

function coerce(row: unknown): Row {
	if (row !== null && typeof row === "object") {
		const out: Row = {};
		for (const [k, v] of Object.entries(row as Record<string, unknown>)) {
			out[k] = typeof v === "number" ? v : String(v);
		}
		return out;
	}
	return { value: typeof row === "number" ? row : String(row) };
}
