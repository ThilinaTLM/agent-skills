import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./swatch.schema.ts";

/**
 * <rd-swatch> — design-token chip. One preview surface on the left, the
 * name and value on the right. Five kinds:
 *
 *   - color:   preview filled with the value as background.
 *   - type:    "Ag" sample rendered with the value as a font shorthand.
 *   - space:   horizontal bar of the value's width.
 *   - radius:  square with the value as border-radius.
 *   - shadow:  square with the value as box-shadow.
 */
class RdSwatch extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const kind = this.getAttribute("kind") || "color";
		const name = this.getAttribute("name") || "";
		const value = this.getAttribute("value") || "";
		const note = this.getAttribute("note");

		this.setAttribute("data-kind", kind);
		this.innerHTML = "";

		const preview = el("div", { class: "_rd-swatch-preview" });
		const inner = el("div", { class: "_rd-swatch-preview-inner" });
		preview.appendChild(inner);
		switch (kind) {
			case "color":
				inner.style.background = value;
				break;
			case "type":
				inner.style.font = value;
				inner.textContent = "Ag";
				break;
			case "space":
				inner.style.width = value;
				inner.classList.add("_rd-swatch-space-bar");
				break;
			case "radius":
				inner.style.borderRadius = value;
				break;
			case "shadow":
				inner.style.boxShadow = value;
				break;
		}

		const text = el(
			"div",
			{ class: "_rd-swatch-text" },
			el("div", { class: "_rd-swatch-name" }, name),
			el("code", { class: "_rd-swatch-value" }, value),
		);
		if (note) text.appendChild(el("div", { class: "_rd-swatch-note" }, note));

		this.appendChild(preview);
		this.appendChild(text);
	}
}

export function register(): void {
	define(tagName, RdSwatch);
}
export { spec, tagName };
