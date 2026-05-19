import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { spec, tagName } from "./quote.schema.ts";

class RdQuote extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		reveal(this);
		const author = this.getAttribute("author");
		const cite = this.getAttribute("cite");
		const url = this.getAttribute("source-url");
		if (author || cite) {
			const parts: (HTMLElement | string | null)[] = [];
			if (author) parts.push(el("span", { class: "_rd-quote-author" }, author));
			if (cite) {
				const citeNode = url
					? el("a", { href: url, target: "_blank", rel: "noopener" }, cite)
					: cite;
				parts.push(el("cite", { class: "_rd-quote-cite" }, citeNode));
			}
			const footer = el(
				"footer",
				{ class: "_rd-quote-attrib" },
				"\u2014\u00a0",
				...parts.flatMap((p, i) =>
					i > 0 ? [el("span", { class: "_rd-quote-sep" }, ", "), p] : [p],
				),
			);
			this.appendChild(footer);
		}
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdQuote);
}
export { spec, tagName };
