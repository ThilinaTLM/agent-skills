import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { spec, tagName } from "./stat.schema.ts";

const TREND_GLYPH: Record<string, string> = {
	up: "\u2191",
	down: "\u2193",
	flat: "\u2192",
};

/** Match a numeric stat value with optional currency prefix and unit
 * suffix. Conservative on purpose — anything that doesn't match (e.g.
 * "complete", "42 days") renders as-is without animation. */
const NUMERIC_VALUE_RE = /^([^\d-]*?)(-?\d+(?:[.,]\d+)?)([^\d]*)$/;

interface NumericValue {
	prefix: string;
	suffix: string;
	target: number;
	decimals: number;
	formatter: (n: number) => string;
}

function parseNumeric(raw: string): NumericValue | null {
	const m = raw.trim().match(NUMERIC_VALUE_RE);
	if (!m) return null;
	const numericPart = m[2].replace(/,/g, "");
	const target = Number(numericPart);
	if (!Number.isFinite(target)) return null;
	const decimalsMatch = numericPart.split(".")[1];
	const decimals = decimalsMatch ? decimalsMatch.length : 0;
	const prefix = m[1] ?? "";
	const suffix = m[3] ?? "";
	const formatter = (n: number) => n.toFixed(decimals);
	return { prefix, suffix, target, decimals, formatter };
}

const COUNT_UP_DURATION_MS = 900;

function easeOutCubic(t: number): number {
	const inv = 1 - t;
	return 1 - inv * inv * inv;
}

function reducedMotion(): boolean {
	if (typeof window === "undefined" || !window.matchMedia) return false;
	return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

class RdStat extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const value = this.getAttribute("value") || "";
		const label = this.getAttribute("label") || "";
		const trend = this.getAttribute("trend");
		const delta = this.getAttribute("delta");
		const tone = this.getAttribute("tone");

		if (tone) this.setAttribute("data-tone", tone);

		this.innerHTML = "";
		if (label) {
			this.appendChild(el("div", { class: "_rd-stat-label" }, label));
		}
		const valueEl = el("div", { class: "_rd-stat-value" }, value);
		this.appendChild(valueEl);
		if (trend || delta) {
			const meta = el("div", { class: "_rd-stat-meta" });
			if (trend) {
				meta.appendChild(
					el("span", { class: "_rd-stat-trend", "data-trend": trend }, TREND_GLYPH[trend] || ""),
				);
			}
			if (delta) {
				meta.appendChild(el("span", { class: "_rd-stat-delta" }, delta));
			}
			this.appendChild(meta);
		}

		// Count-up animation. Numeric values animate from 0 → target on
		// reveal; non-numeric values just appear. Reduced-motion users
		// see the final value immediately.
		const parsed = parseNumeric(value);
		if (parsed && !reducedMotion()) {
			valueEl.textContent = `${parsed.prefix}${parsed.formatter(0)}${parsed.suffix}`;
			reveal(this, () => runCountUp(valueEl, parsed));
		} else {
			reveal(this);
		}
		this._upgraded = true;
	}
}

function runCountUp(target: HTMLElement, parsed: NumericValue): void {
	const start = performance.now();
	const render = (now: number) => {
		const elapsed = Math.min(1, (now - start) / COUNT_UP_DURATION_MS);
		const value = parsed.target * easeOutCubic(elapsed);
		target.textContent = `${parsed.prefix}${parsed.formatter(value)}${parsed.suffix}`;
		if (elapsed < 1) requestAnimationFrame(render);
	};
	requestAnimationFrame(render);
}

export function register(): void {
	define(tagName, RdStat);
}
export { spec, tagName };
