import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { spec, tagName } from "./progress.schema.ts";

/**
 * <rd-progress> — linear progress / capacity bar.
 *
 * Accepts `value` as either a 0..1 decimal ("0.6") or a fraction
 * ("12/20"). Renders a label/value pair above the bar; the bar fill
 * count-up-animates from 0 → target on entry into the viewport.
 */

interface Parsed {
	pct: number;
	displayValue: string;
}

function parseValue(raw: string): Parsed {
	const trimmed = raw.trim();
	const fraction = trimmed.match(/^(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)$/);
	if (fraction) {
		const a = Number(fraction[1]);
		const b = Number(fraction[2]);
		if (Number.isFinite(a) && Number.isFinite(b) && b > 0) {
			return { pct: Math.max(0, Math.min(1, a / b)) * 100, displayValue: `${a} / ${b}` };
		}
	}
	const pctMatch = trimmed.match(/^(-?\d+(?:\.\d+)?)\s*%$/);
	if (pctMatch) {
		const n = Number(pctMatch[1]);
		return { pct: Math.max(0, Math.min(100, n)), displayValue: `${n}%` };
	}
	const num = Number(trimmed);
	if (Number.isFinite(num)) {
		const pct = num > 1 ? Math.max(0, Math.min(100, num)) : Math.max(0, Math.min(1, num)) * 100;
		return { pct, displayValue: `${Math.round(pct)}%` };
	}
	return { pct: 0, displayValue: trimmed };
}

function reducedMotion(): boolean {
	if (typeof window === "undefined" || !window.matchMedia) return false;
	return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

class RdProgress extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;

		const valueAttr = this.getAttribute("value") || "0";
		const label = this.getAttribute("label");
		const tone = this.getAttribute("tone");
		const { pct, displayValue } = parseValue(valueAttr);

		if (tone) this.setAttribute("data-tone", tone);
		this.innerHTML = "";

		const meta = el("div", { class: "_rd-progress-meta" });
		meta.appendChild(el("span", { class: "_rd-progress-label" }, label || ""));
		const valueEl = el("span", { class: "_rd-progress-value" }, displayValue);
		meta.appendChild(valueEl);
		this.appendChild(meta);

		const track = el("div", { class: "_rd-progress-track" });
		const fill = el("div", { class: "_rd-progress-fill" });
		track.appendChild(fill);
		this.appendChild(track);

		// ARIA — back the visual with native semantics.
		this.setAttribute("role", "progressbar");
		this.setAttribute("aria-valuemin", "0");
		this.setAttribute("aria-valuemax", "100");
		this.setAttribute("aria-valuenow", String(Math.round(pct)));
		if (label) this.setAttribute("aria-label", label);

		if (reducedMotion()) {
			fill.style.width = `${pct}%`;
		} else {
			fill.style.width = "0%";
			reveal(this, () => {
				// Use CSS transition for the fill itself; transition is set
				// in progress.css.
				requestAnimationFrame(() => {
					fill.style.width = `${pct}%`;
				});
			});
		}
	}
}

export function register(): void {
	define(tagName, RdProgress);
}
export { spec, tagName };
