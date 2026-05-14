import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./margin.schema.ts";

/**
 * <rd-margin> — Tufte-style sidenote.
 *
 * On wide viewports (≥ 1024px) the note floats into the page gutter, just
 * like a printed margin gloss. On narrow viewports it collapses to a small
 * inline marker that opens a popover with the note's content — keeping
 * the prose uninterrupted but the aside discoverable. The popover uses
 * the platform's native [popover] attribute (light-dismiss, ESC to close).
 */

const NARROW_MQ = "(max-width: 1023.98px)";
const INFO_SVG =
	'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>';

let counter = 0;

class RdMargin extends HTMLElement implements Upgradeable {
	_upgraded = false;
	private _mq: MediaQueryList | null = null;
	private _onMq: (() => void) | null = null;

	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;

		const id = `_rd-margin-${++counter}`;

		// Move authored children into a dedicated note container. One node,
		// two presentations: floated sidenote on wide, popover on narrow.
		const note = el("div", { class: "_rd-margin-note", id });
		while (this.firstChild) note.appendChild(this.firstChild);

		// Inline marker that triggers the popover on narrow viewports. The
		// button stays in the accessibility tree at all widths so screen
		// readers always have an explicit affordance — it just becomes
		// `display: none` (via CSS) on wide screens where the note is
		// already visible alongside the prose.
		const marker = el("button", {
			type: "button",
			class: "_rd-margin-marker",
			"aria-label": "Show margin note",
			popovertarget: id,
		});
		marker.innerHTML = INFO_SVG;

		this.appendChild(marker);
		this.appendChild(note);

		// Toggle popover semantics on the note element based on viewport. We
		// only add the `popover` attribute at narrow widths so the note
		// participates in normal flow / floats at wide widths without the
		// popover top-layer machinery interfering.
		if (typeof window !== "undefined" && window.matchMedia) {
			this._mq = window.matchMedia(NARROW_MQ);
			this._onMq = () => {
				if (this._mq?.matches) {
					note.setAttribute("popover", "auto");
				} else {
					// Closing first avoids "Failed to remove popover" warnings
					// if the popover was open when the viewport widened.
					if (note.matches(":popover-open")) {
						try {
							(note as HTMLElement & { hidePopover(): void }).hidePopover();
						} catch {
							/* hidePopover unsupported — ignore */
						}
					}
					note.removeAttribute("popover");
				}
			};
			this._onMq();
			this._mq.addEventListener("change", this._onMq);
		} else {
			// SSR / very old browsers: leave the note in flow.
		}
	}

	disconnectedCallback() {
		if (this._mq && this._onMq) {
			this._mq.removeEventListener("change", this._onMq);
		}
		this._mq = null;
		this._onMq = null;
	}
}

export function register(): void {
	define(tagName, RdMargin);
}
export { spec, tagName };
