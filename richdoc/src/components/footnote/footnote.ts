import { type Upgradeable, define, el } from "../../lib/base.ts";
import { attachTooltip } from "../../lib/tooltip.ts";
import { spec, tagName } from "./footnote.schema.ts";

/**
 * <rd-footnote> renders a small inline marker (typically a superscript
 * number) that links to a numbered entry collected in a "Notes" section at
 * the bottom of the enclosing <rd-page>.
 *
 * On upgrade the original inline content is moved into a per-page
 * <rd-footnotes><ol/></rd-footnotes> container, which is created lazily on
 * first use. Markers are numbered in document order. A back-link arrow on
 * each entry returns the reader to the marker.
 *
 * If a `mark` attribute is set, that text is used verbatim instead of the
 * auto-incremented number (useful for *, †, ‡, or named marks).
 */

interface PageWithFootnoteState extends HTMLElement {
	_rdFootnoteCount?: number;
	_rdFootnotesContainer?: HTMLElement;
}

class RdFootnote extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;

		const page = (this.closest("rd-page") || document.body) as PageWithFootnoteState;
		const customMark = this.getAttribute("mark");
		const num = (page._rdFootnoteCount = (page._rdFootnoteCount || 0) + 1);
		const fnId = `fn-${num}`;
		const refId = `fnref-${num}`;

		// Inline marker — clickable link down to the entry.
		const marker = el("a", {
			class: "_rd-fn-marker",
			href: `#${fnId}`,
			id: refId,
		});
		if (customMark) {
			marker.textContent = customMark;
			marker.setAttribute("data-custom-mark", "");
		} else {
			marker.textContent = String(num);
		}

		// Find-or-create the footnotes block at the bottom of the page.
		let container = page._rdFootnotesContainer;
		if (!container || !container.isConnected) {
			container = page.querySelector<HTMLElement>(":scope > rd-footnotes");
			if (!container) {
				container = el(
					"rd-footnotes",
					{},
					el("div", { class: "_rd-footnotes-title" }, "Notes"),
					el("ol", { class: "_rd-footnotes-list" }),
				);
				page.appendChild(container);
			}
			page._rdFootnotesContainer = container;
		}
		const list = container.querySelector<HTMLElement>("ol._rd-footnotes-list");
		if (!list) return;

		// Move the original inline content into the new <li>.
		const item = el("li", { id: fnId, class: "_rd-fn-item" });
		while (this.firstChild) item.appendChild(this.firstChild);

		// Back-link arrow returning to the inline marker.
		const back = el(
			"a",
			{
				class: "_rd-fn-back",
				href: `#${refId}`,
				"aria-label": "Back to reference",
			},
			"↩",
		);
		item.appendChild(document.createTextNode(" "));
		item.appendChild(back);
		list.appendChild(item);

		// Build a preview body for the hover/focus tooltip. We clone the
		// rendered <li> content minus the back-link so the canonical entry
		// at the foot of the page remains untouched.
		const preview = document.createElement("div");
		for (const node of Array.from(item.childNodes)) {
			if (
				node instanceof HTMLElement &&
				node.classList.contains("_rd-fn-back")
			)
				continue;
			preview.appendChild(node.cloneNode(true));
		}

		// Replace the inline element's content with just the marker.
		this.appendChild(marker);

		// Hover/focus the marker to read the note inline; click still
		// navigates to #fn-N so mobile and keyboard "activate" behave.
		attachTooltip(marker, preview, {
			clickToToggle: false,
			popupClass: "_rd-fn-preview",
		});
	}
}

export function register(): void {
	define(tagName, RdFootnote);
}
export { spec, tagName };
