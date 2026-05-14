import { type Upgradeable, define, el } from "../../lib/base.ts";
import { spec, tagName, taskSpec, taskTagName } from "./checklist.schema.ts";

class RdChecklist extends HTMLElement {
	// Pure layout — children handle their own upgrade.
}

class RdTask extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		const done = this.hasAttribute("done");
		const assignee = this.getAttribute("assignee");
		const due = this.getAttribute("due");
		if (done) this.setAttribute("data-done", "");

		// The box always carries the check icon; it's revealed via CSS when
		// the task is marked done. Using <rd-icon> keeps the stroke weight
		// and rendering identical to every other glyph in the system.
		const checkIcon = document.createElement("rd-icon");
		checkIcon.setAttribute("name", "check");
		checkIcon.setAttribute("size", "sm");
		checkIcon.setAttribute("aria-hidden", "true");
		const box = el("span", { class: "_rd-task-box", "aria-hidden": "true" }, checkIcon);

		// Move existing inline content into a body wrapper so we can append meta.
		const body = el("span", { class: "_rd-task-body" });
		while (this.firstChild) body.appendChild(this.firstChild);

		const meta: HTMLElement[] = [];
		if (assignee) {
			meta.push(el("span", { class: "_rd-task-meta-item", "data-kind": "assignee" }, assignee));
		}
		if (due) {
			meta.push(el("span", { class: "_rd-task-meta-item", "data-kind": "due" }, due));
		}
		if (meta.length > 0) {
			body.appendChild(el("span", { class: "_rd-task-meta" }, ...meta));
		}

		this.appendChild(box);
		this.appendChild(body);
		this._upgraded = true;
	}
}

export function register(): void {
	define(tagName, RdChecklist);
	define(taskTagName, RdTask);
}
export { spec, tagName, taskSpec, taskTagName };
