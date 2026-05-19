import { loadCdnScript } from "../../lib/cdn.ts";
import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { escapeHtml, parseLineRanges, stripCommonIndent } from "../../lib/text.ts";
import { spec, tagName } from "./code.schema.ts";

interface HljsApi {
	highlight: (
		code: string,
		opts: { language: string; ignoreIllegals?: boolean },
	) => { value: string };
	highlightAuto: (code: string) => { value: string; language?: string };
	getLanguage: (name: string) => unknown;
}

const HLJS_URL =
	"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.10.0/build/highlight.min.js";

function loadHljs(): Promise<HljsApi | null> {
	const win = window as typeof window & { hljs?: HljsApi };
	return loadCdnScript<HljsApi>(HLJS_URL, () => win.hljs);
}

function wrapLines(html: string, start: number, highlighted: Set<number>): string {
	// Note: line spans are joined with no separator. The parent <pre> uses
	// white-space: pre, so any literal "\n" between display:block line spans
	// would render as an extra blank line and double the visual line height.
	const lines = html.split("\n");
	const out: string[] = [];
	for (let i = 0; i < lines.length; i++) {
		const n = start + i;
		const hl = highlighted.has(n) ? ' data-highlight=""' : "";
		out.push(`<span class="_rd-code-line" data-line="${n}"${hl}>${lines[i] || " "}</span>`);
	}
	return out.join("");
}

class RdCode extends HTMLElement implements Upgradeable {
	_upgraded = false;
	async connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const lang = this.getAttribute("lang") || "";
		const title = this.getAttribute("title") || "";
		const showLineNumbers = this.hasAttribute("line-numbers");
		const startAttr = this.getAttribute("start");
		const start = startAttr ? Number(startAttr) || 1 : 1;
		const highlightSet = parseLineRanges(this.getAttribute("highlight"));
		const source = stripCommonIndent(this.textContent || "").replace(/\s+$/, "");

		const copyBtn = el(
			"button",
			{
				class: "_rd-code-copy",
				type: "button",
				"aria-label": "Copy code",
				onclick: async () => {
					try {
						await navigator.clipboard.writeText(source);
						copyBtn.textContent = "Copied";
						copyBtn.setAttribute("data-copied", "");
						setTimeout(() => {
							copyBtn.textContent = "Copy";
							copyBtn.removeAttribute("data-copied");
						}, 1200);
					} catch {
						copyBtn.textContent = "Failed";
						setTimeout(() => {
							copyBtn.textContent = "Copy";
						}, 1200);
					}
				},
			},
			"Copy",
		);

		const header = el("div", { class: "_rd-code-header" });
		if (lang) {
			header.appendChild(el("span", { class: "_rd-code-lang" }, lang));
		}
		if (title) {
			header.appendChild(el("span", { class: "_rd-code-title" }, title));
		}
		if (!lang && !title) {
			header.appendChild(el("span", { class: "_rd-code-lang" }, "code"));
		}
		header.appendChild(copyBtn);

		// First pass: get highlighted markup (or escaped source) as HTML.
		let bodyHtml = escapeHtml(source);
		if (lang) {
			const hljs = await loadHljs();
			if (hljs?.getLanguage(lang)) {
				try {
					bodyHtml = hljs.highlight(source, { language: lang, ignoreIllegals: true }).value;
				} catch {
					/* fall through to escaped */
				}
			}
		}

		// Wrap each line so we can style highlight + numbers via CSS.
		if (showLineNumbers || highlightSet.size > 0) {
			bodyHtml = wrapLines(bodyHtml, start, highlightSet);
		}

		const code = document.createElement("code");
		if (lang) code.className = `language-${lang} hljs`;
		else code.className = "hljs";
		code.innerHTML = bodyHtml;

		const pre = document.createElement("pre");
		pre.className = "_rd-code-body";
		if (showLineNumbers) pre.setAttribute("data-line-numbers", "");
		pre.appendChild(code);

		this.innerHTML = "";
		this.appendChild(header);
		this.appendChild(pre);
	}
}

export function register(): void {
	define(tagName, RdCode);
}
export { spec, tagName };
