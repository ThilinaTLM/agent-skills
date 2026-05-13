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

		const box = el(
			"span",
			{
				class: "_rd-task-box",
				"aria-hidden": "true",
			},
			done ? "\u2713" : "",
		);

		// Move existing inline content into a body wrapper so we can append meta.
		const body = el("span", { class: "_rd-task-body" });
		while (this.firstChild) body.appendChild(this.firstChild);

		const meta: HTMLElement[] = [];
		if (assignee) {
			meta.push(el("span", { class: "_rd-task-meta-item" }, `@${assignee}`));
		}
		if (due) {
			meta.push(el("span", { class: "_rd-task-meta-item" }, due));
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
