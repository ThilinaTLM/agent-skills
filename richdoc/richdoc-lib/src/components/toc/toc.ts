import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { slugify } from "../../lib/text.ts";
import { spec, tagName } from "./toc.schema.ts";

class RdToc extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		queueMicrotask(() => this._build());
	}

	_build() {
		const levels = (this.getAttribute("levels") || "2,3")
			.split(",")
			.map((s) => Number.parseInt(s.trim(), 10))
			.filter((n) => n >= 1 && n <= 6)
			.sort((a, b) => a - b);
		if (levels.length === 0) return;
		const title = this.getAttribute("title") || "On this page";

		const root = this.closest("rd-page") || document.body;
		const sel = levels.map((l) => `h${l}`).join(",");
		const headings = Array.from(root.querySelectorAll<HTMLElement>(sel)).filter(
			(h) => !this.contains(h),
		);
		if (headings.length === 0) return;

		const depthOf = (lvl: number) => levels.indexOf(lvl);

		const rootUl = el("ul");
		const ulAtDepth: (HTMLElement | undefined)[] = [rootUl];

		for (const h of headings) {
			const level = Number.parseInt(h.tagName.slice(1), 10);
			const depth = depthOf(level);
			if (depth < 0) continue;
			if (!h.id) {
				h.id = slugify(h.textContent || "") || `h-${Math.random().toString(36).slice(2, 7)}`;
			}
			const li = el(
				"li",
				{},
				el(
					"a",
					{ href: `#${h.id}` },
					el("span", { class: "_rd-toc-text" }, h.textContent || ""),
					el("span", { class: "_rd-toc-leader", "aria-hidden": "true" }),
				),
			);

			if (depth === 0) {
				rootUl.appendChild(li);
				ulAtDepth[0] = rootUl;
				ulAtDepth.length = 1;
			} else {
				let parentDepth = depth - 1;
				while (parentDepth >= 0 && !ulAtDepth[parentDepth]) parentDepth--;
				if (parentDepth < 0) {
					rootUl.appendChild(li);
					continue;
				}
				const parentUl = ulAtDepth[parentDepth];
				if (!parentUl) {
					rootUl.appendChild(li);
					continue;
				}
				const parentLi = parentUl.lastElementChild as HTMLElement | null;
				if (!parentLi) {
					parentUl.appendChild(li);
					continue;
				}
				let nested = parentLi.querySelector<HTMLElement>(":scope > ul");
				if (!nested) {
					nested = el("ul");
					parentLi.appendChild(nested);
				}
				nested.appendChild(li);
				ulAtDepth[depth] = nested;
				ulAtDepth.length = depth + 1;
			}
		}

		this.innerHTML = "";
		this.appendChild(el("div", { class: "_rd-toc-title" }, title));
		this.appendChild(rootUl);
	}
}

export function register(): void {
	define(tagName, RdToc);
}
export { spec, tagName };
