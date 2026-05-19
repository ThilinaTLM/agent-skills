import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { nodeSpec, nodeTagName, spec, tagName } from "./tree.schema.ts";

class RdTree extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const title = this.getAttribute("title");
		if (title) this.prepend(el("div", { class: "_rd-tree-title" }, title));
	}
}

/**
 * <rd-node> renders its `label` as a `<details>` summary, with any nested
 * <rd-node> children as the disclosure body. Leaf nodes (no rd-node
 * children) render as a plain row with no chevron.
 */
class RdNode extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const label = this.getAttribute("label") || "";
		const open = this.hasAttribute("open");
		const iconName = this.getAttribute("icon");

		const hasChildren = this.querySelector(":scope > rd-node") !== null;
		this.setAttribute("data-leaf", hasChildren ? "false" : "true");

		// Build the summary row. For leaves we still emit a div so the
		// CSS layout is uniform.
		const labelEl = el("span", { class: "_rd-tree-label" }, label);
		const iconEl = iconName ? document.createElement("rd-icon") : null;
		if (iconEl) {
			iconEl.setAttribute("name", iconName as string);
			iconEl.setAttribute("size", "sm");
			iconEl.setAttribute("aria-hidden", "true");
			iconEl.className = "_rd-tree-icon";
		}

		if (!hasChildren) {
			const row = el("div", { class: "_rd-tree-row" });
			if (iconEl) row.appendChild(iconEl);
			row.appendChild(labelEl);
			this.prepend(row);
			return;
		}

		const chevron = document.createElement("rd-icon");
		chevron.setAttribute("name", "chevron-right");
		chevron.setAttribute("size", "sm");
		chevron.setAttribute("aria-hidden", "true");
		chevron.className = "_rd-tree-chevron";

		const summary = el("summary", { class: "_rd-tree-row" }, chevron);
		if (iconEl) summary.appendChild(iconEl);
		summary.appendChild(labelEl);

		const details = el("details", open ? { open: true } : {});
		details.appendChild(summary);
		// Move all <rd-node> children into the details so they live inside
		// the disclosure body. Non-node children (rare) follow them.
		while (this.firstChild) details.appendChild(this.firstChild);
		this.appendChild(details);
	}
}

export function register(): void {
	define(tagName, RdTree);
	define(nodeTagName, RdNode);
}

export { spec, tagName, nodeSpec, nodeTagName };
