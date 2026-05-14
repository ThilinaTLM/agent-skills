import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { spec, tagName } from "./decision.schema.ts";

/**
 * <rd-decision> — ADR-style decision record header + rationale block.
 *
 * Renders a header strip with: ID + status pill on the left, date + deciders
 * on the right, then the title in display Fraunces, then the element's
 * remaining body content as rationale.
 */
class RdDecision extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const status = this.getAttribute("status") || "proposed";
		const id = this.getAttribute("id");
		const date = this.getAttribute("date");
		const deciders = this.getAttribute("deciders");
		const title = this.getAttribute("title");
		this.setAttribute("data-status", status);

		const body = el("div", { class: "_rd-decision-body" });
		while (this.firstChild) body.appendChild(this.firstChild);

		const meta = el("div", { class: "_rd-decision-meta" });
		if (id) meta.appendChild(el("span", { class: "_rd-decision-id" }, id));
		meta.appendChild(el("span", { class: "_rd-decision-status" }, status));

		const sub = el("div", { class: "_rd-decision-sub" });
		if (date) sub.appendChild(el("time", { class: "_rd-decision-date", datetime: date }, date));
		if (deciders) sub.appendChild(el("span", { class: "_rd-decision-deciders" }, deciders));

		const header = el("div", { class: "_rd-decision-header" }, meta);
		if (sub.children.length) header.appendChild(sub);

		this.appendChild(header);
		if (title) this.appendChild(el("h3", { class: "_rd-decision-title" }, title));
		this.appendChild(body);
	}
}

export function register(): void {
	define(tagName, RdDecision);
}
export { spec, tagName };
