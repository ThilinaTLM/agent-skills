import { type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tabSpec, tabTagName, tagName } from "./tabs.schema.ts";

class RdTabs extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const tabs = Array.from(this.querySelectorAll<HTMLElement>(":scope > rd-tab"));
		if (tabs.length === 0) {
			this._upgraded = true;
			return;
		}

		let activeIdx = tabs.findIndex((t) => t.hasAttribute("active"));
		if (activeIdx < 0) activeIdx = 0;

		const strip = el("div", { class: "_rd-tab-strip", role: "tablist" });
		const buttons: HTMLButtonElement[] = [];

		const select = (idx: number) => {
			tabs.forEach((tab, i) => {
				if (i === idx) tab.removeAttribute("hidden");
				else tab.setAttribute("hidden", "");
				buttons[i].setAttribute("aria-selected", String(i === idx));
				buttons[i].setAttribute("tabindex", i === idx ? "0" : "-1");
			});
		};

		tabs.forEach((tab, i) => {
			const label = tab.getAttribute("label") || `Tab ${i + 1}`;
			const id = tab.id || `rd-tab-${Math.random().toString(36).slice(2, 8)}-${i}`;
			tab.id = id;
			tab.setAttribute("role", "tabpanel");
			const btn = el(
				"button",
				{
					type: "button",
					role: "tab",
					"aria-controls": id,
					"aria-selected": String(i === activeIdx),
					tabindex: i === activeIdx ? "0" : "-1",
					onclick: () => select(i),
					onkeydown: (ev: Event) => {
						const e = ev as KeyboardEvent;
						if (e.key === "ArrowRight") {
							e.preventDefault();
							const next = (i + 1) % tabs.length;
							select(next);
							buttons[next].focus();
						} else if (e.key === "ArrowLeft") {
							e.preventDefault();
							const prev = (i - 1 + tabs.length) % tabs.length;
							select(prev);
							buttons[prev].focus();
						}
					},
				},
				label,
			) as HTMLButtonElement;
			buttons.push(btn);
			strip.appendChild(btn);
		});

		this.prepend(strip);
		select(activeIdx);
		this._upgraded = true;
	}
}

class RdTab extends HTMLElement {}

export function register(): void {
	define(tagName, RdTabs);
	define(tabTagName, RdTab);
}
export { spec, tagName, tabSpec, tabTagName };
