import { loadCdnScript } from "../../lib/cdn.ts";
import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { escapeHtml, stripCommonIndent } from "../../lib/text.ts";
import { spec, tagName } from "./diff.schema.ts";

interface HljsApi {
	highlight: (
		code: string,
		opts: { language: string; ignoreIllegals?: boolean },
	) => { value: string };
	getLanguage: (name: string) => unknown;
}

const HLJS_URL =
	"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.10.0/build/highlight.min.js";

function loadHljs(): Promise<HljsApi | null> {
	const win = window as typeof window & { hljs?: HljsApi };
	return loadCdnScript<HljsApi>(HLJS_URL, () => win.hljs);
}

type LineKind = "add" | "del" | "hunk" | "ctx";

function classify(line: string): LineKind {
	if (line.startsWith("+++") || line.startsWith("---")) return "hunk";
	if (line.startsWith("@@")) return "hunk";
	const c = line[0];
	if (c === "+") return "add";
	if (c === "-") return "del";
	return "ctx";
}

function copyToClipboard(text: string, btn: HTMLElement) {
	if (!navigator.clipboard) return;
	navigator.clipboard.writeText(text).then(() => {
		const prev = btn.textContent;
		btn.textContent = "Copied";
		btn.setAttribute("data-copied", "");
		setTimeout(() => {
			btn.textContent = prev;
			btn.removeAttribute("data-copied");
		}, 1200);
	});
}

class RdDiff extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const lang = this.getAttribute("lang") || "";
		const title = this.getAttribute("title") || "";
		const showLineNumbers = this.hasAttribute("line-numbers");
		const source = stripCommonIndent(this.textContent || "").replace(/\s+$/, "");
		this.textContent = "";

		// Header bar.
		const labelText = title || (lang ? `${lang} · diff` : "diff");
		const header = el(
			"div",
			{ class: "_rd-code-header" },
			el("span", { class: "_rd-code-label" }, labelText),
		);
		const copyBtn = el(
			"button",
			{
				class: "_rd-code-copy",
				type: "button",
				"aria-label": "Copy diff",
				onclick: () => copyToClipboard(source, copyBtn),
			},
			"Copy",
		);
		header.appendChild(copyBtn);
		this.appendChild(header);

		const pre = el("pre", { class: "_rd-diff-body" });
		if (showLineNumbers) pre.setAttribute("data-line-numbers", "");
		const lines = source.split("\n");

		// Highlight line content (excluding marker) if a language is set.
		let hljs: HljsApi | null = null;
		if (lang) {
			hljs = await loadHljs();
		}

		// Walk the diff with paired (old, new) cursors so each line carries the
		// real file line number it represents. `+` lines have only a new number,
		// `-` lines only an old number, context has both. Hunk markers reseed
		// the cursors from `@@ -X,Y +A,B @@`.
		let oldLine = 1;
		let newLine = 1;

		for (let i = 0; i < lines.length; i++) {
			const line = lines[i];
			const kind = classify(line);
			if (kind === "hunk") {
				const m = line.match(/^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)/);
				if (m) {
					oldLine = Number(m[1]);
					newLine = Number(m[2]);
				}
			}

			let oldNum = "";
			let newNum = "";
			if (showLineNumbers && kind !== "hunk") {
				if (kind === "add") {
					newNum = String(newLine++);
				} else if (kind === "del") {
					oldNum = String(oldLine++);
				} else {
					oldNum = String(oldLine++);
					newNum = String(newLine++);
				}
			}

			const marker = kind === "hunk" ? "" : (line[0] ?? " ");
			const body = kind === "hunk" ? line : line.slice(1);
			let bodyHtml: string;
			if (hljs && lang && hljs.getLanguage(lang) && kind !== "hunk") {
				try {
					bodyHtml = hljs.highlight(body, { language: lang, ignoreIllegals: true }).value;
				} catch {
					bodyHtml = escapeHtml(body);
				}
			} else {
				bodyHtml = escapeHtml(body);
			}
			const lineEl = document.createElement("span");
			lineEl.className = "_rd-diff-line";
			lineEl.setAttribute("data-kind", kind);
			const numsHtml = showLineNumbers
				? `<span class="_rd-diff-nums" aria-hidden="true"><span class="_rd-diff-num _rd-diff-num-old">${escapeHtml(oldNum)}</span><span class="_rd-diff-num _rd-diff-num-new">${escapeHtml(newNum)}</span></span>`
				: "";
			lineEl.innerHTML = `${numsHtml}<span class="_rd-diff-marker">${escapeHtml(marker)}</span><span class="_rd-diff-content">${bodyHtml}</span>`;
			// No "\n" text node between lines — the parent <pre> preserves
			// whitespace, which would render the newline as an extra blank line
			// between display:block line spans.
			pre.appendChild(lineEl);
		}

		this.appendChild(pre);
	}
}

export function register(): void {
	define(tagName, RdDiff);
}
export { spec, tagName };
