import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { stripCommonIndent } from "../../lib/text.ts";
import {
	outputSpec,
	outputTagName,
	promptSpec,
	promptTagName,
	spec,
	tagName,
} from "./shell.schema.ts";

/**
 * <rd-shell> renders a terminal session: a panel with an optional title
 * bar, then alternating <rd-prompt> lines (with $ glyph + cwd) and
 * <rd-output> blocks (dimmer monospace, preserving whitespace).
 *
 * Deliberately distinct from <rd-code> — no syntax highlighting, no
 * line numbers, no copy button. Reads as a transcript, not a snippet.
 */
class RdShell extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const title = this.getAttribute("title");
		if (title) this.prepend(el("div", { class: "_rd-shell-title" }, title));
	}
}

class RdPrompt extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const cwd = this.getAttribute("cwd");
		const command = stripCommonIndent(this.textContent || "").trim();
		this.innerHTML = "";
		if (cwd) this.appendChild(el("span", { class: "_rd-shell-cwd" }, cwd));
		this.appendChild(el("span", { class: "_rd-shell-glyph", "aria-hidden": "true" }, "$"));
		this.appendChild(el("span", { class: "_rd-shell-command" }, command));
	}
}

class RdOutput extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const tone = this.getAttribute("tone");
		if (tone) this.setAttribute("data-tone", tone);
		// Preserve whitespace by wrapping in <pre>. Move children over so
		// any inline HTML the author provided still works.
		const pre = el("pre", { class: "_rd-shell-output-body" });
		const raw = this.textContent || "";
		const dedented = stripCommonIndent(raw).replace(/^\n+|\n+$/g, "");
		this.innerHTML = "";
		pre.textContent = dedented;
		this.appendChild(pre);
	}
}

export function register(): void {
	define(tagName, RdShell);
	define(promptTagName, RdPrompt);
	define(outputTagName, RdOutput);
}

export { spec, tagName, promptSpec, promptTagName, outputSpec, outputTagName };
