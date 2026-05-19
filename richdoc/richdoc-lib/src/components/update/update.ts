import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { reveal } from "../../lib/reveal.ts";
import { spec, tagName } from "./update.schema.ts";

const UPDATE_ICONS: Record<string, string> = {
	release: "package",
	change: "git-commit",
	note: "bell",
};

/**
 * <rd-update> — reverse-chron status entry. Pairs date + author with a
 * rich body. Distinct from <rd-event> (which lives inside <rd-timeline>
 * with a hollow-circle marker on a vertical rule): updates are for
 * changelogs, release notes, status reports.
 */
class RdUpdate extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const date = this.getAttribute("date") || "";
		const author = this.getAttribute("author");
		const title = this.getAttribute("title");
		const kind = this.getAttribute("kind") || "note";
		this.setAttribute("data-kind", kind);

		// Move children into the body wrapper before we prepend the gutter.
		const body = el("div", { class: "_rd-update-body" });
		while (this.firstChild) body.appendChild(this.firstChild);

		const iconName = UPDATE_ICONS[kind] || UPDATE_ICONS.note;
		const icon = document.createElement("rd-icon");
		icon.setAttribute("name", iconName);
		icon.setAttribute("size", "sm");
		icon.setAttribute("aria-hidden", "true");

		const gutter = el(
			"div",
			{ class: "_rd-update-gutter" },
			el("div", { class: "_rd-update-kind" }, icon, document.createTextNode(kind)),
			el("time", { class: "_rd-update-date", datetime: date }, date),
		);
		if (author) gutter.appendChild(el("div", { class: "_rd-update-author" }, author));

		if (title) body.prepend(el("h3", { class: "_rd-update-title" }, title));

		this.appendChild(gutter);
		this.appendChild(body);

		reveal(this);
	}
}

export function register(): void {
	define(tagName, RdUpdate);
}
export { spec, tagName };
