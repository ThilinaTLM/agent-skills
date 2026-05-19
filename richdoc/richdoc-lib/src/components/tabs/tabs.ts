import { type Upgradeable, define, el } from "../../lib/dom.ts";
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
		const indicator = el("span", {
			class: "_rd-tab-indicator",
			"aria-hidden": "true",
		});

		const moveIndicator = (idx: number) => {
			const btn = buttons[idx];
			if (!btn) return;
			const stripRect = strip.getBoundingClientRect();
			const btnRect = btn.getBoundingClientRect();
			// Position relative to the strip so the indicator slides
			// regardless of how the strip itself is positioned on the page.
			const x = btnRect.left - stripRect.left;
			indicator.style.setProperty("--rd-tab-indicator-x", `${x}px`);
			indicator.style.setProperty("--rd-tab-indicator-w", `${btnRect.width}px`);
		};

		const select = (idx: number) => {
			tabs.forEach((tab, i) => {
				if (i === idx) tab.removeAttribute("hidden");
				else tab.setAttribute("hidden", "");
				buttons[i].setAttribute("aria-selected", String(i === idx));
				buttons[i].setAttribute("tabindex", i === idx ? "0" : "-1");
			});
			moveIndicator(idx);
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

		strip.appendChild(indicator);
		this.prepend(strip);
		select(activeIdx);

		// Re-measure on resize so the indicator stays glued to the active
		// tab even as the strip reflows under responsive breakpoints.
		const ro = new ResizeObserver(() => {
			const current = buttons.findIndex((b) => b.getAttribute("aria-selected") === "true");
			if (current >= 0) moveIndicator(current);
		});
		ro.observe(strip);

		// First measurement after the strip lays out.
		requestAnimationFrame(() => moveIndicator(activeIdx));

		this._upgraded = true;
	}
}

class RdTab extends HTMLElement {}

export function register(): void {
	define(tagName, RdTabs);
	define(tabTagName, RdTab);
}
export { spec, tagName, tabSpec, tabTagName };
