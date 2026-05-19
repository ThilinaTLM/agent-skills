import { type Upgradeable, define, el } from "../../lib/dom.ts";
import { attachTooltip } from "../tooltip/tooltip-service.ts";
import { citeSpec, citeTagName, refSpec, refTagName, spec, tagName } from "./references.schema.ts";

/**
 * Bibliography + citation primitives.
 *
 * Three tags work as a system:
 *
 *   - <rd-ref key="…" author="…" title="…" url="…" date="…">…</rd-ref>
 *       Entry declaration. Author writes these anywhere; they're
 *       invisible inline and only render in the bibliography.
 *
 *   - <rd-cite key="…">                  [N]
 *       Inline citation marker. Numbered by first appearance in document
 *       order. Hover shows the full reference as a tooltip; click jumps
 *       to the bibliography entry.
 *
 *   - <rd-references title="…">          (optional placement)
 *       Explicit position for the bibliography. If the doc has an
 *       <rd-references>, the list renders inside it. Otherwise the list
 *       is auto-appended to the foot of the enclosing <rd-page>.
 *
 * Numbering is per-page and resolves on a `requestAnimationFrame` cycle
 * after all elements have upgraded, so order is stable regardless of
 * declaration order in the source.
 */

interface PageWithRefState extends HTMLElement {
	_rdRefsResolved?: boolean;
	_rdRefsScheduled?: boolean;
}

function schedulePageResolve(page: PageWithRefState): void {
	if (page._rdRefsScheduled) return;
	page._rdRefsScheduled = true;
	requestAnimationFrame(() => {
		try {
			resolvePage(page);
		} catch (err) {
			console.warn("[richdoc] reference resolver failed", err);
		}
	});
}

function resolvePage(page: PageWithRefState): void {
	if (page._rdRefsResolved) return;
	page._rdRefsResolved = true;

	const cites = Array.from(page.querySelectorAll<RdCite>("rd-cite"));
	const refs = Array.from(page.querySelectorAll<RdRef>("rd-ref"));

	// Index entries by key.
	const byKey = new Map<string, RdRef>();
	for (const r of refs) {
		const key = r.getAttribute("key");
		if (key && !byKey.has(key)) byKey.set(key, r);
	}

	// Assign numbers in citation order.
	const order = new Map<string, number>();
	for (const c of cites) {
		const key = c.getAttribute("key");
		if (!key) continue;
		if (!order.has(key)) order.set(key, order.size + 1);
	}
	// Any refs not cited still appear at the end, in declaration order.
	for (const [key] of byKey) {
		if (!order.has(key)) order.set(key, order.size + 1);
	}

	if (order.size === 0) return;

	// Build the bibliography container.
	const list = el("ol", { class: "_rd-refs-list" });
	for (const [key, num] of order) {
		const r = byKey.get(key);
		const id = `ref-${num}`;
		const li = el("li", { id, class: "_rd-ref-item", "data-key": key });
		if (r) renderEntry(li, r);
		else li.appendChild(el("span", { class: "_rd-ref-missing" }, `[missing: ${key}]`));
		list.appendChild(li);
	}

	const explicitHost = page.querySelector<HTMLElement>("rd-references");
	let host: HTMLElement;
	if (explicitHost) {
		const title = explicitHost.getAttribute("title") || "References";
		explicitHost.innerHTML = "";
		explicitHost.appendChild(el("div", { class: "_rd-refs-title" }, title));
		explicitHost.appendChild(list);
		host = explicitHost;
	} else {
		const auto = el(
			"rd-references",
			{ "data-auto": "" },
			el("div", { class: "_rd-refs-title" }, "References"),
			list,
		);
		page.appendChild(auto);
		host = auto;
	}

	// Replace each <rd-cite> with its numbered marker and a tooltip preview.
	for (const c of cites) {
		const key = c.getAttribute("key");
		if (!key) continue;
		const num = order.get(key);
		if (num === undefined) continue;
		const fnId = `ref-${num}`;
		const refId = `refmark-${num}-${Math.random().toString(36).slice(2, 6)}`;
		const marker = el("a", { class: "_rd-cite-marker", href: `#${fnId}`, id: refId }, `[${num}]`);
		c.innerHTML = "";
		c.appendChild(marker);

		// Build the tooltip preview from the bibliography entry.
		const entry = host.querySelector<HTMLElement>(`li[data-key="${cssEscape(key)}"]`);
		if (entry) {
			const preview = entry.cloneNode(true) as HTMLElement;
			// Strip the back-link from the preview.
			preview.querySelector("._rd-ref-back")?.remove();
			attachTooltip(marker, preview, {
				clickToToggle: false,
				popupClass: "_rd-ref-preview",
			});
		}
	}

	// Hide refs from inline flow (they're declarations, not content).
	for (const r of refs) r.setAttribute("hidden", "");
}

function renderEntry(li: HTMLElement, r: RdRef): void {
	const author = r.getAttribute("author");
	const title = r.getAttribute("title");
	const url = r.getAttribute("url");
	const date = r.getAttribute("date");
	const publisher = r.getAttribute("publisher");

	if (author) {
		li.appendChild(el("span", { class: "_rd-ref-author" }, author));
		li.appendChild(document.createTextNode(". "));
	}
	if (title) {
		const t = el("em", { class: "_rd-ref-title" }, title);
		li.appendChild(t);
		li.appendChild(document.createTextNode(". "));
	}
	if (publisher) {
		li.appendChild(el("span", { class: "_rd-ref-publisher" }, publisher));
		li.appendChild(document.createTextNode(". "));
	}
	if (date) {
		li.appendChild(el("span", { class: "_rd-ref-date" }, date));
		li.appendChild(document.createTextNode(". "));
	}

	// Body text content (if any) — for notes / annotations.
	const body = (r.textContent || "").trim();
	if (body) {
		li.appendChild(document.createTextNode(" "));
		li.appendChild(el("span", { class: "_rd-ref-note" }, body));
	}

	if (url) {
		li.appendChild(document.createTextNode(" "));
		li.appendChild(
			el("a", { class: "_rd-ref-url", href: url, target: "_blank", rel: "noopener" }, url),
		);
	}
}

function cssEscape(s: string): string {
	if (typeof CSS !== "undefined" && CSS.escape) return CSS.escape(s);
	return s.replace(/["\\]/g, "\\$&");
}

/**
 * <rd-cite> — placeholder until the page-level resolver runs. Its
 * `connectedCallback` schedules a single resolve pass for the enclosing
 * <rd-page>; the resolver does the heavy lifting.
 */
class RdCite extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const page = this.closest("rd-page") as PageWithRefState | null;
		if (page) schedulePageResolve(page);
	}
}

/** <rd-ref> — declarations are hidden once the resolver inlines them
 *  into the bibliography. Until then they remain in flow with their raw
 *  text content, which is harmless. */
class RdRef extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const page = this.closest("rd-page") as PageWithRefState | null;
		if (page) schedulePageResolve(page);
	}
}

/** Empty placeholder that the resolver fills with the bibliography list. */
class RdReferences extends HTMLElement implements Upgradeable {
	_upgraded = false;
	connectedCallback() {
		if (this._upgraded) return;
		this._upgraded = true;
		const page = this.closest("rd-page") as PageWithRefState | null;
		if (page) schedulePageResolve(page);
	}
}

export function register(): void {
	define(tagName, RdReferences);
	define(refTagName, RdRef);
	define(citeTagName, RdCite);
}

export { spec, tagName, refSpec, refTagName, citeSpec, citeTagName };
