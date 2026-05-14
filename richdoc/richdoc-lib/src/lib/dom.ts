/**
 * DOM primitives shared across components.
 *
 * Tiny on purpose — these helpers ship in the bundle. New helpers should
 * earn their weight by being used in at least two components.
 */

type ElProps = Record<string, string | number | boolean | null | undefined | ((ev: Event) => void)>;
type ElChild = Node | string | null | undefined;

/** Lightweight DOM builder. Mirrors React.createElement ergonomics. */
export function el(tag: string, props: ElProps = {}, ...children: ElChild[]): HTMLElement {
	const node = document.createElement(tag);
	for (const [k, v] of Object.entries(props)) {
		if (v === undefined || v === null || v === false) continue;
		if (k === "class") node.className = String(v);
		else if (k === "html") node.innerHTML = String(v);
		else if (k.startsWith("on") && typeof v === "function") {
			node.addEventListener(k.slice(2).toLowerCase(), v as EventListener);
		} else {
			node.setAttribute(k, v === true ? "" : String(v));
		}
	}
	for (const c of children) {
		if (c == null) continue;
		node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
	}
	return node;
}

/** Register a custom element only once. */
export function define(name: string, ctor: CustomElementConstructor): void {
	if (!customElements.get(name)) customElements.define(name, ctor);
}

/** Idempotency flag used by every component to guard against double-upgrade. */
export interface Upgradeable extends HTMLElement {
	_upgraded?: boolean;
}
