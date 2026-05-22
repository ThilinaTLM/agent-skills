import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./detail.schema.ts";

/**
 * <rd-detail> — collapsible disclosure built on native <details>.
 *
 * Four variants share one element:
 *   - panel    (default) — bordered panel with header strip + chevron
 *   - hairline           — bracketed by top/bottom hairlines, no panel
 *   - question           — hairline + Fraunces display summary (Q/A entry)
 *   - reveal             — eye icon, summary toggles to "Hide" when open
 *
 * All variants are pure HTML <details> under the hood, so they work
 * without JS.
 */
class RdDetail extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const variant = this.getAttribute("variant") || "panel";
		const userSummary = this.getAttribute("summary");
		const summaryText = userSummary || (variant === "reveal" ? "Reveal" : "Details");
		const open = this.hasAttribute("open");
		const details = el("details", open ? { open: true } : {}) as HTMLDetailsElement;

		// Summary structure: label on the left, an affordance glyph on the
		// right. The glyph is a real <rd-icon> so its stroke weight, size,
		// and theming match every other glyph in the framework.
		const isReveal = variant === "reveal";
		const glyph = document.createElement("rd-icon");
		glyph.setAttribute("name", isReveal ? "eye" : "chevron-down");
		glyph.setAttribute("size", "sm");
		glyph.setAttribute("aria-hidden", "true");
		glyph.className = "_rd-detail-chevron";

		const textEl = el("span", { class: "_rd-detail-text" }, summaryText);
		const summaryEl = el("summary", { class: "_rd-detail-summary" }, textEl, glyph);
		details.appendChild(summaryEl);
		// Move existing children into the details wrapper.
		while (this.firstChild) details.appendChild(this.firstChild);
		this.appendChild(details);
		this.setAttribute("data-variant", variant);

		if (isReveal) {
			// "Reveal" ⇄ "Hide" label toggle on open/close. The base label
			// stays whatever the author authored (or the "Reveal" default).
			const baseLabel = summaryText;
			const sync = () => {
				textEl.textContent = details.open ? "Hide" : baseLabel;
			};
			details.addEventListener("toggle", sync);
			sync();
		}

		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdDetail);
}
export { spec, tagName };
