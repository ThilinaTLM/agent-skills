import { type Upgradeable, define } from "../../lib/base.ts";
import { spec, tagName } from "./page.schema.ts";

/**
 * <rd-page> is the only legal child of <body>. It mirrors its `theme`
 * and `mode` attributes onto <html data-theme> / <html data-mode> so the
 * token rules in tokens.css can hang off :root selectors.
 *
 * Precedence (highest to lowest):
 *   1. attribute on <rd-page>
 *   2. attribute already on <html> (set by the doc author directly)
 *   3. system @media (prefers-color-scheme: dark)
 *
 * If <rd-page> has no theme/mode attribute, the existing <html> attrs are
 * left alone — the doc author may set them globally and the page won't
 * stomp on that.
 */

/** First N top-level children get the entry cascade. Anything past that
 * is already below the fold on common viewports and would only delay
 * paint without a payoff. */
const ENTER_CASCADE_LIMIT = 8;
/** Per-child delay in ms; total cascade ≈ LIMIT * STEP + duration. */
const ENTER_CASCADE_STEP_MS = 20;

class RdPage extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;

		const theme = this.getAttribute("theme");
		const mode = this.getAttribute("mode");
		if (theme) document.documentElement.setAttribute("data-theme", theme);
		if (mode) document.documentElement.setAttribute("data-mode", mode);

		// Page-enter cascade. Tag the first N direct element children with
		// data-rd-enter and an incremental --rd-enter-delay; CSS hides them
		// until data-rd-entered flips on the page. The cascade is short
		// (≈180ms + 20ms stagger) so reading isn't blocked.
		const kids = Array.from(this.children).filter(
			(c): c is HTMLElement => c instanceof HTMLElement && c.tagName !== "RD-FOOTNOTES",
		);
		for (let i = 0; i < Math.min(kids.length, ENTER_CASCADE_LIMIT); i++) {
			const k = kids[i];
			k.setAttribute("data-rd-enter", "");
			k.style.setProperty("--rd-enter-delay", `${i * ENTER_CASCADE_STEP_MS}ms`);
		}
		// Flip on the next frame so the initial CSS state actually applies
		// before the transition target is set.
		requestAnimationFrame(() => {
			requestAnimationFrame(() => this.setAttribute("data-rd-entered", ""));
		});
	}
}

export function register(): void {
	define(tagName, RdPage);
}
export { spec, tagName };
