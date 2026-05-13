import { type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tagName } from "./stat.schema.ts";

const TREND_GLYPH: Record<string, string> = {
	up: "\u2191",
	down: "\u2193",
	flat: "\u2192",
};

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
		this.appendChild(el("div", { class: "_rd-stat-value" }, value));
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
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdStat);
}
export { spec, tagName };
