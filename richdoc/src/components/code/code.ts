import { type Upgradeable, define, el, stripCommonIndent } from "../../lib/base.ts";
import { spec, tagName } from "./code.schema.ts";

class RdCode extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const lang = this.getAttribute("lang") || "";
		const title = this.getAttribute("title") || "";
		const source = stripCommonIndent(this.textContent || "");

		const copyBtn = el(
			"button",
			{
				class: "_rd-code-copy",
				type: "button",
				onclick: async () => {
					try {
						await navigator.clipboard.writeText(source);
						copyBtn.textContent = "Copied";
						setTimeout(() => {
							copyBtn.textContent = "Copy";
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

		const label = [title, lang].filter(Boolean).join(" · ") || "code";
		const header = el(
			"div",
			{ class: "_rd-code-header" },
			el("span", { class: "_rd-code-label" }, label),
			copyBtn,
		);
		const pre = el("pre", {}, el("code", {}, source));

		this.innerHTML = "";
		this.appendChild(header);
		this.appendChild(pre);
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdCode);
}
export { spec, tagName };
