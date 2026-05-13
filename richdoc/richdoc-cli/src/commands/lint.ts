import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { defineCommand } from "citty";
import { type HTMLElement, parse } from "node-html-parser";
import { jsonError, jsonOk } from "../lib/output.ts";
import { ALLOWED_TAGS, SCHEMA, isRdTag } from "../lib/schema.ts";
import type { LintIssue } from "../types/index.ts";

export const lintCommand = defineCommand({
	meta: {
		name: "lint",
		description:
			"Validate a richdoc .html file against the rd-* component schema.",
	},
	args: {
		file: {
			type: "positional",
			description: "Path to the .html file to lint",
			required: true,
		},
	},
	async run({ args }) {
		const file = resolve(args.file);
		let source: string;
		try {
			source = await readFile(file, "utf8");
		} catch (err) {
			const reason = err instanceof Error ? err.message : "unknown error";
			jsonError(`Could not read file: ${reason}`, "INPUT_ERROR");
		}

		const issues: LintIssue[] = [];
		const root = parse(source, {
			lowerCaseTagName: false,
			comment: false,
		});

		// Line-number index for the source.
		const lineOffsets = buildLineOffsets(source);
		const lineOf = (offset: number): number => {
			// Binary search the line offsets.
			let lo = 0;
			let hi = lineOffsets.length - 1;
			while (lo < hi) {
				const mid = (lo + hi + 1) >>> 1;
				if (lineOffsets[mid] <= offset) lo = mid;
				else hi = mid - 1;
			}
			return lo + 1;
		};

		// --- Document-level checks ----------------------------------------

		const head = root.querySelector("head");
		const links = head ? head.getElementsByTagName("link") : [];
		const scripts = head ? head.getElementsByTagName("script") : [];

		const cssLinked = links.some(
			(l) =>
				(l.getAttribute("rel") || "").toLowerCase() === "stylesheet" &&
				(l.getAttribute("href") || "").toLowerCase().includes("richdoc.css"),
		);
		const jsLinked = scripts.some((s) =>
			(s.getAttribute("src") || "").toLowerCase().includes("richdoc.js"),
		);
		if (!cssLinked) {
			issues.push({
				severity: "error",
				rule: "missing-css",
				message:
					'richdoc.css is not linked in <head>. Add: <link rel="stylesheet" href="./richdoc.css">',
			});
		}
		if (!jsLinked) {
			issues.push({
				severity: "error",
				rule: "missing-js",
				message:
					'richdoc.js is not linked in <head>. Add: <script src="./richdoc.js" defer></script>',
			});
		}

		const pages = root.querySelectorAll("rd-page");
		if (pages.length === 0) {
			issues.push({
				severity: "error",
				rule: "missing-rd-page",
				message: "Document has no <rd-page>. Wrap your content in <rd-page>.",
			});
		} else if (pages.length > 1) {
			issues.push({
				severity: "warn",
				rule: "multiple-rd-page",
				message: `Document has ${pages.length} <rd-page> elements; usually exactly one is expected.`,
			});
		}
		for (const p of pages) {
			const parent = p.parentNode as HTMLElement | null;
			if (parent?.tagName && parent.tagName.toLowerCase() !== "body") {
				issues.push({
					severity: "warn",
					rule: "rd-page-not-under-body",
					tag: "rd-page",
					line: lineOf(p.range?.[0] ?? 0),
					message: `<rd-page> should be directly under <body> (found under <${parent.tagName.toLowerCase()}>).`,
				});
			}
		}

		// --- Walk every element -------------------------------------------

		walk(root, (node) => {
			if (!node.tagName) return;
			const tag = node.tagName.toLowerCase();
			if (!isRdTag(tag)) return;

			const line = lineOf(node.range?.[0] ?? 0);

			if (!ALLOWED_TAGS.includes(tag)) {
				issues.push({
					severity: "error",
					rule: "unknown-tag",
					tag,
					line,
					message: `Unknown richdoc tag <${tag}>. Allowed: ${ALLOWED_TAGS.join(", ")}.`,
				});
				return;
			}

			const spec = SCHEMA[tag];
			if (!spec) return;

			// Required attributes
			for (const a of spec.required ?? []) {
				const v = node.getAttribute(a);
				if (v === undefined || v === null || v === "") {
					issues.push({
						severity: "error",
						rule: "missing-required-attr",
						tag,
						attr: a,
						line,
						message: `<${tag}> is missing required attribute '${a}'.`,
					});
				}
			}

			// Unknown attributes (warning)
			const known = new Set([
				...(spec.required ?? []),
				...(spec.optional ?? []),
			]);
			for (const a of Object.keys(node.attributes)) {
				if (
					a.startsWith("data-") ||
					a === "id" ||
					a === "class" ||
					a === "style"
				)
					continue;
				if (!known.has(a)) {
					issues.push({
						severity: "warn",
						rule: "unknown-attr",
						tag,
						attr: a,
						line,
						message: `<${tag}> has unknown attribute '${a}'. Known: ${[...known].join(", ") || "(none)"}.`,
					});
				}
			}

			// Enum validation
			for (const [a, allowed] of Object.entries(spec.enums ?? {})) {
				const v = node.getAttribute(a);
				if (v !== undefined && v !== null && v !== "" && !allowed.includes(v)) {
					issues.push({
						severity: "error",
						rule: "invalid-attr-value",
						tag,
						attr: a,
						line,
						message: `<${tag} ${a}="${v}"> is invalid. Allowed values: ${allowed.join(", ")}.`,
					});
				}
			}

			// Parent constraint
			if (spec.allowedParents) {
				const parent = node.parentNode as HTMLElement | null;
				const parentTag = parent?.tagName?.toLowerCase() ?? "";
				if (!spec.allowedParents.includes(parentTag)) {
					issues.push({
						severity: "error",
						rule: "wrong-parent",
						tag,
						line,
						message: `<${tag}> must be a direct child of ${spec.allowedParents
							.map((p) => `<${p}>`)
							.join(" or ")} (found inside <${parentTag || "?"}>).`,
					});
				}
			}

			// Custom-children constraint (only constrains rd-* children;
			// plain HTML children are always allowed).
			if (Array.isArray(spec.customChildren)) {
				const allowedChildren = spec.customChildren;
				for (const child of node.childNodes) {
					const childEl = child as HTMLElement;
					if (!childEl.tagName) continue;
					const ct = childEl.tagName.toLowerCase();
					if (isRdTag(ct) && !allowedChildren.includes(ct)) {
						issues.push({
							severity: "error",
							rule: "wrong-child",
							tag,
							line: lineOf(childEl.range?.[0] ?? 0),
							message: `<${ct}> is not allowed inside <${tag}>. Allowed rd-* children: ${allowedChildren
								.map((c) => `<${c}>`)
								.join(", ")}.`,
						});
					}
				}
			}
		});

		const errors = issues.filter((i) => i.severity === "error").length;
		const warnings = issues.filter((i) => i.severity === "warn").length;

		if (errors > 0) {
			jsonError(
				`Lint failed: ${errors} error${errors === 1 ? "" : "s"}, ${warnings} warning${warnings === 1 ? "" : "s"}.`,
				"LINT_ERRORS",
				undefined,
				{ file, errors, warnings, issues },
			);
		}

		jsonOk({
			file,
			errors,
			warnings,
			issues,
		});
	},
});

function walk(node: HTMLElement, fn: (node: HTMLElement) => void): void {
	fn(node);
	for (const child of node.childNodes) {
		const c = child as HTMLElement;
		if (c.tagName) walk(c, fn);
	}
}

function buildLineOffsets(source: string): number[] {
	const offsets: number[] = [0];
	for (let i = 0; i < source.length; i++) {
		if (source.charCodeAt(i) === 10 /* \n */) offsets.push(i + 1);
	}
	return offsets;
}
