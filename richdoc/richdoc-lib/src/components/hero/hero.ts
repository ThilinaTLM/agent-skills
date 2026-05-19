import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./hero.schema.ts";

/**
 * <rd-hero> — magazine-style top-of-page header. Replaces the ad-hoc
 * <h1> + <rd-kv> opener with a coordinated display block.
 *
 * Attributes:
 *   - eyebrow?  Small caps kicker above the title.
 *   - title     The main title; renders at display opsz 144.
 *   - lede?     One-sentence intro in Fraunces italic.
 *   - meta?     Quiet meta line (e.g. "Updated Jan 2026 · Platform team").
 *
 * Any inline children remain after the meta line — useful for an
 * <rd-kv> or <rd-badge> strip directly under the hero.
 */
class RdHero extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const eyebrow = this.getAttribute("eyebrow");
		const title = this.getAttribute("title") || "";
		const lede = this.getAttribute("lede");
		const meta = this.getAttribute("meta");

		// Capture any pre-existing children (e.g. an <rd-kv>) before we
		// rebuild the host's internals.
		const extras = Array.from(this.childNodes);
		this.innerHTML = "";

		if (eyebrow) this.appendChild(el("div", { class: "_rd-hero-eyebrow" }, eyebrow));
		this.appendChild(el("h1", { class: "_rd-hero-title" }, title));
		if (lede) this.appendChild(el("p", { class: "_rd-hero-lede" }, lede));
		if (meta) this.appendChild(el("div", { class: "_rd-hero-meta" }, meta));
		if (extras.length) {
			const extrasWrap = el("div", { class: "_rd-hero-extras" });
			for (const node of extras) extrasWrap.appendChild(node);
			this.appendChild(extrasWrap);
		}
	}
}

export function register(): void {
	define(tagName, RdHero);
}
export { spec, tagName };
