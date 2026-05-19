import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { eventSpec, eventTagName, spec, tagName } from "./timeline.schema.ts";

class RdTimeline extends HTMLElement {}

class RdEvent extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		reveal(this);
		const date = this.getAttribute("date") || "";
		const title = this.getAttribute("title") || "";
		if (date || title) {
			this.prepend(
				el(
					"div",
					{ class: "_rd-event-meta" },
					date ? el("span", { class: "_rd-event-date" }, date) : null,
					title ? el("span", { class: "_rd-event-title" }, title) : null,
				),
			);
		}
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdTimeline);
	define(eventTagName, RdEvent);
}
export { spec, tagName, eventSpec, eventTagName };
